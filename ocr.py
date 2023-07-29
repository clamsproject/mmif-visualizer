import datetime
import pathlib

import cv2
import tempfile
import json
import re
import html

from flask import render_template, session
from mmif.utils.video_document_helper import convert_timepoint, convert_timeframe
# from utils import app


class OCRFrame():
    """Class representing an (aligned or otherwise) set of OCR annotations for a single frame"""

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
        if anno.at_type.shortname == "BoundingBox":
            self.add_bounding_box(anno, mmif)

        elif anno.at_type.shortname == "TimeFrame":
            self.add_timeframe(anno, mmif)

        elif anno.at_type.shortname == "TextDocument":
            t = anno.properties.get("text_value") or anno.properties.get("text").value
            if t:
                self.text.append(re.sub(r'([\\\/\|\"\'])', r'\1 ', t))

    def add_bounding_box(self, anno, mmif):
        self.frame_num = convert_timepoint(mmif, anno, "frames")
        self.secs = convert_timepoint(mmif, anno, "seconds")
        box_id = anno.properties["id"]
        boxType = anno.properties["boxType"]
        coordinates = anno.properties["coordinates"]
        x = coordinates[0][0]
        y = coordinates[0][1]
        w = coordinates[3][0] - x
        h = coordinates[3][1] - y
        box = [box_id, boxType, [x, y, w, h]]
        self.boxes.append(box)
        self.anno_ids.append(box_id)
        self.timestamp = str(datetime.timedelta(seconds=self.secs))
        if anno.properties.get("boxType") and anno.properties.get("boxType") not in self.boxtypes:
            self.boxtypes.append(anno.properties.get("boxType"))


    def add_timeframe(self, anno, mmif):
        start, end = convert_timeframe(mmif, anno, "frames")
        start_secs, end_secs = convert_timeframe(mmif, anno, "seconds")
        self.range = (start, end)
        self.timestamp_range = (str(datetime.timedelta(seconds=start_secs)), str(datetime.timedelta(seconds=end_secs)))
        self.sec_range = (start_secs, end_secs)
        if anno.properties.get("frameType"):
            self.frametype = anno.properties.get("frameType")


def find_annotation(anno_id, view, mmif):
    if mmif.id_delimiter in anno_id:
        view_id, anno_id = anno_id.split(mmif.id_delimiter)
        view = mmif.get_view_by_id(view_id)
    return view.get_annotation_by_id(anno_id)


def get_ocr_frames(view, mmif, fps):
    frames = {}
    full_alignment_type = [
        at_type for at_type in view.metadata.contains if at_type.shortname == "Alignment"]
    # If view contains alignments
    if full_alignment_type:
        for alignment in view.get_annotations(full_alignment_type[0]):
            source = find_annotation(alignment.properties["source"], view, mmif)
            target = find_annotation(alignment.properties["target"], view, mmif)
            
            frame = OCRFrame(source, mmif)
            i = frame.frame_num if frame.frame_num is not None else frame.range
            if i in frames.keys():
                frames[i].update(source, mmif)
                frames[i].update(target, mmif)
            else:
                frame.update(target, mmif)
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
    """Generate pages from a list of frames"""
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

def render_ocr(vid_path, view_id, page_number):
    """Iterate through frames and display the contents/alignments."""
    # Path for storing temporary images generated by cv2
    cv2_vid = cv2.VideoCapture(vid_path)
    f = open(session[f"{view_id}-page-file"])
    frames_pages = json.load(f)
    page = frames_pages[str(page_number)]
    prev_frame_cap = None
    for frame_num, frame in page:
        # If index is range instead of frame...
        if frame.get("range"):
            frame_num = (int(frame["range"][0]) + int(frame["range"][1])) / 2
        cv2_vid.set(1, frame_num)
        _, frame_cap = cv2_vid.read()
        if frame_cap is None:
            raise FileNotFoundError(f"Video file {vid_path} not found!")

        # Double check histogram similarity of "repeat" frames -- if they're significantly different, un-mark as repeat
        if prev_frame_cap is not None and frame["repeat"] and not is_duplicate_image(prev_frame_cap, frame_cap, cv2_vid):
            frame["repeat"] = False

        with tempfile.NamedTemporaryFile(
                prefix=str(pathlib.Path(__file__).parent /'static'/'tmp'), suffix=".jpg", delete=False) as tf:
            cv2.imwrite(tf.name, frame_cap)
            # "id" is just the name of the temp image file
            frame["id"] = pathlib.Path(tf.name).name
        prev_frame_cap = frame_cap

    return render_template('ocr.html',
                           vid_path=vid_path,
                           view_id=view_id,
                           page=page,
                           n_pages=len(frames_pages),
                           page_number=str(page_number))


def find_duplicates(frames_list, cv2_vid):
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
    if abs(len(prev_frame.get("boxes"))-len(frame.get("boxes"))) > 3:
        return False
    # Check Boundingbox distances
    rounded_prev = round_boxes(prev_frame.get("boxes"))
    for box in round_boxes(frame.get("boxes")):
        if box in rounded_prev and frame["secs"]-prev_frame["secs"] < 10:
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
    hist_img1 = cv2.calcHist([img1_hsv], [0,1], None, [180,256], [0,180,0,256])
    cv2.normalize(hist_img1, hist_img1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX);
    hist_img2 = cv2.calcHist([img2_hsv], [0,1], None, [180,256], [0,180,0,256])
    cv2.normalize(hist_img2, hist_img2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX);

    # Find the metric value
    metric_val = cv2.compareHist(hist_img1, hist_img2, cv2.HISTCMP_CHISQR)
    return metric_val < 50



def round_boxes(boxes):
    # To account for jittery bounding boxes in OCR annotations
    rounded_boxes = []
    for box in boxes:
        rounded_box = []
        for coord in box[2]:
            rounded_box.append(round(coord/100)*100)
        rounded_boxes.append(rounded_box)
    return rounded_boxes


def get_ocr_views(mmif):
    """Return OCR views, which have TextDocument, BoundingBox, and Alignment annotations"""
    views = []
    required_types = ["TimeFrame", "BoundingBox", "TextDocument"]
    ocr_apps = ["east", "tesseract", "chyron", "slate", "bars", "parseq"]
    for view in mmif.views:
        if (any([ocr_app in view.metadata.app for ocr_app in ocr_apps]) and 
                any([anno_type.shortname in required_types for anno_type in view.metadata.contains.keys()])):
            views.append(view)
    return views

def save_json(dict, view_id):
    with tempfile.NamedTemporaryFile(prefix=str(pathlib.Path(__file__).parent /'static'/'tmp'), suffix=".json", delete=False) as tf:
        pages_json = open(tf.name, "w")
        json.dump(dict, pages_json)
        session[f"{view_id}-page-file"] = tf.name
