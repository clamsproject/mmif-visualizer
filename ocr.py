import datetime

import cv2
import json
import re
import os
import shutil
from mmif.vocabulary.annotation_types import AnnotationTypes
from mmif.vocabulary.document_types import DocumentTypes

from mmif.utils.video_document_helper import convert_timepoint, convert_timeframe

import cache

"""
Helper function for showing debug information

def some_function(x):
    from utils import app  # import inside function
    app.logger.debug(x)
"""

class OCRFrame():
    """
    Class representing an (aligned or otherwise) set of OCR annotations for a single frame
    """

    def __init__(self, anno, mmif):
        self.text = []
        self.boxes = []
        self.anno_ids = []
        self.timestamp = None
        self.secs = None
        self.repeat = False
        self.frame_num = None
        self.range = None
        self.timestamp_range = None
        self.sec_range = None
        self.frametype = None
        self.boxtypes = []

        self.update(anno, mmif)

    def update(self, anno, mmif):

        if anno.at_type == AnnotationTypes.BoundingBox:
            self.add_bounding_box(anno, mmif)

        elif anno.at_type == AnnotationTypes.TimeFrame:
            self.add_timeframe(anno, mmif)

        elif anno.at_type == AnnotationTypes.TimePoint:
            self.add_timepoint(anno, mmif)

        elif anno.at_type == DocumentTypes.TextDocument:
            self.add_text_document(anno)

        elif anno.at_type.shortname == "Paragraph":
            view = mmif.get_view_by_id(anno.parent)
            text_anno = view.get_annotation_by_id(
                anno.properties.get("document"))
            self.add_text_document(text_anno)

    def add_bounding_box(self, anno, mmif):
        if "timePoint" in anno.properties:
            timepoint_anno = mmif[anno.get("timePoint")]
            
            if timepoint_anno:
                self.add_timepoint(timepoint_anno, mmif,
                                   skip_if_view_has_frames=False)
        else:
            for alignment_anns in mmif.get_alignments(AnnotationTypes.BoundingBox, AnnotationTypes.TimePoint).values():
                for alignment_ann in alignment_anns:
                    if alignment_ann.get('source') == anno.long_id:
                        timepoint_anno = mmif[alignment_ann.get('target')]
                        break
                    elif alignment_ann.get('target') == anno.long_id:
                        timepoint_anno = mmif[alignment_ann.get('source')]
                        break
        if timepoint_anno:
            self.add_timepoint(timepoint_anno, mmif, skip_if_view_has_frames=False)

        box_id = anno.get("id")
        boxType = anno.get("boxType")
        coordinates = anno.get("coordinates")
        x = coordinates[0][0]
        y = coordinates[0][1]
        w = coordinates[1][0] - x
        h = coordinates[1][1] - y
        box = [box_id, boxType, [x, y, w, h]]
        self.boxes.append(box)
        self.anno_ids.append(box_id)
        self.timestamp = str(datetime.timedelta(seconds=self.secs))
        if anno.properties.get("boxType") and anno.properties.get("boxType") not in self.boxtypes:
            self.boxtypes.append(anno.properties.get("boxType"))

    def add_timeframe(self, anno, mmif):
        # If annotation has multiple targets, pick the first and last as start and end
        if "targets" in anno.properties:
            start_id, end_id = anno.properties.get(
                "targets")[0], anno.properties.get("targets")[-1]
            anno_parent = mmif.get_view_by_id(anno.parent)
            start_anno, end_anno = anno_parent.get_annotation_by_id(start_id), anno_parent.get_annotation_by_id(end_id)
            start = convert_timepoint(mmif, start_anno, "frames")
            end = convert_timepoint(mmif, end_anno, "frames")
            start_secs = convert_timepoint(mmif, start_anno, "seconds")
            end_secs = convert_timepoint(mmif, end_anno, "seconds")
        else:
            start, end = convert_timeframe(mmif, anno, "frames")
            start_secs, end_secs = convert_timeframe(mmif, anno, "seconds")
        self.range = (start, end)
        self.timestamp_range = (str(datetime.timedelta(seconds=start_secs)), str(
            datetime.timedelta(seconds=end_secs)))
        self.sec_range = (start_secs, end_secs)
        if anno.properties.get("frameType"):
            self.frametype = str(anno.properties.get("frameType"))
        elif anno.properties.get("label"):
            self.frametype = str(anno.properties.get("label"))

    def add_timepoint(self, anno, mmif, skip_if_view_has_frames=True):
        parent = mmif.get_view_by_id(anno.parent)
        other_annotations = [
            k for k in parent.metadata.contains.keys() if k != anno.id]
        # If there are TimeFrames in the same view, they most likely represent
        # condensed information about representative frames (e.g. SWT). In this
        # case, only render the TimeFrames and ignore the TimePoints.
        if any([anno.shortname == "TimeFrame" for anno in other_annotations]) and skip_if_view_has_frames:
            return
        self.frame_num = convert_timepoint(mmif, anno, "frames")
        self.secs = convert_timepoint(mmif, anno, "seconds")
        self.timestamp = str(datetime.timedelta(seconds=self.secs))
        if anno.properties.get("label"):
            self.frametype = anno.properties.get("label")

    def add_text_document(self, anno):
        t = anno.properties.get(
            "text_value") or anno.properties.get("text").value
        if t:
            text_val = re.sub(r'([\\\/\|\"\'])', r'\1 ', t)
            self.text = self.text + \
                [text_val] if text_val not in self.text else self.text


def prepare_ocr(mmif, view, viz_id):
    """
    Prepares list of frames that will be passed back and forth between server
    and client, and renders the first page of the OCR.
    """
    ocr_frames = get_ocr_frames(view, mmif)

    # Generate pages (necessary to reduce IO cost) and render
    frames_list = [(k, vars(v)) for k, v in ocr_frames.items()]
    frames_list = find_duplicates(frames_list)
    frames_pages = paginate(frames_list)
    # Save page list as temp file
    save_json(frames_pages, view.id, viz_id)



def get_ocr_frames(view, mmif):
    frames = {}
    full_alignment_type = [
        at_type for at_type in view.metadata.contains if at_type == AnnotationTypes.Alignment]
    # If view contains alignments
    if full_alignment_type:
        for alignment in view.get_annotations(full_alignment_type[0]):
            source = mmif[alignment.get("source")]
            target = mmif[alignment.get("target")]

            # Account for alignment in either direction
            frame = OCRFrame(source, mmif)
            if target.at_type == DocumentTypes.TextDocument:
                frame.add_timepoint(source, mmif, skip_if_view_has_frames=False)
            frame.update(target, mmif)

            i = frame.frame_num if frame.frame_num is not None else frame.range
            if i is None:
                continue
            if i in frames.keys():
                frames[i].update(source, mmif)
                frames[i].update(target, mmif)
            else:
                frames[i] = frame

    else:
        for annotation in view.get_annotations():
            frame = OCRFrame(annotation, mmif)
            i = frame.frame_num if frame.frame_num is not None else frame.range
            if i is None:
                continue
            if i in frames.keys():
                frames[i].update(annotation, mmif)
            else:
                frames[i] = frame
    return frames


def paginate(frames_list):
    """
    Generate pages from a list of frames
    """
    pages = [[]]
    n_frames_on_page = 0
    for frame_num, frame in frames_list:
        if n_frames_on_page >= 4 and not frame["repeat"]:
            pages.append([])
            n_frames_on_page = 0

        pages[-1].append((frame_num, frame))

        if not frame["repeat"]:
            n_frames_on_page += 1

    return {i: page for (i, page) in enumerate(pages)}


def make_image_directory(mmif_id, view_id):
    # Make path for temp OCR image files or clear image files if it exists
    path = cache.get_cache_root() / mmif_id / "img" / view_id
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    return path


def find_duplicates(frames_list):
    """Find duplicate frames"""
    prev_frame = None
    for frame_num, frame in frames_list:
        # Frame is timeframe annotation
        if type(frame_num) != int:
            continue
        if is_duplicate_ocr_frame(prev_frame, frame):
            frame["repeat"] = True
        prev_frame = frame
    return frames_list


def is_duplicate_ocr_frame(prev_frame, frame):
    if not prev_frame:
        return False
    if prev_frame.get("boxtypes") != frame.get("boxtypes"):
        return False
    if abs(len(prev_frame.get("boxes")) - len(frame.get("boxes"))) > 3:
        return False
    # Check Boundingbox distances
    rounded_prev = round_boxes(prev_frame.get("boxes"))
    for box in round_boxes(frame.get("boxes")):
        if box in rounded_prev and frame["secs"] - prev_frame["secs"] < 10:
            return True
    # Check overlap in text
    prev_text, text = set(prev_frame.get("text")), set(frame.get("text"))
    if prev_text and text and prev_text.intersection(text):
        return True
    return False


def is_duplicate_image(prev_frame, frame, cv2_vid):
    # Convert it to HSV
    img1_hsv = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2HSV)
    img2_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Calculate the histogram and normalize it
    hist_img1 = cv2.calcHist([img1_hsv], [0, 1], None, [
                             180, 256], [0, 180, 0, 256])
    cv2.normalize(hist_img1, hist_img1, alpha=0,
                  beta=1, norm_type=cv2.NORM_MINMAX)
    hist_img2 = cv2.calcHist([img2_hsv], [0, 1], None, [
                             180, 256], [0, 180, 0, 256])
    cv2.normalize(hist_img2, hist_img2, alpha=0,
                  beta=1, norm_type=cv2.NORM_MINMAX)

    # Find the metric value
    metric_val = cv2.compareHist(hist_img1, hist_img2, cv2.HISTCMP_CHISQR)
    return metric_val < 50


def round_boxes(boxes):
    """
    To account for jittery bounding boxes in OCR annotations
    """
    rounded_boxes = []
    for box in boxes:
        rounded_box = []
        for coord in box[2]:
            rounded_box.append(round(coord / 100) * 100)
        rounded_boxes.append(rounded_box)
    return rounded_boxes


def save_json(data, view_id, mmif_id):
    path = cache.get_cache_root() / mmif_id / f"{view_id}-pages.json"
    with open(path, 'w') as f:
        json.dump(data, f)
