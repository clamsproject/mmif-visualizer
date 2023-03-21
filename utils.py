import os
import sys
import datetime
import secrets

import cv2


from io import StringIO
from string import Template

import displacy
import requests
import tempfile
import re
import ast
import html

from flask import Flask, request, render_template, flash, redirect, jsonify
from werkzeug.utils import secure_filename

from mmif.serialize import Mmif, View
from mmif.vocabulary import AnnotationTypes
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri

FORWARD = 1

# Get Properties from MMIF file ---

# these two static folder-related params are important, do not remove
app = Flask(__name__, static_folder='static', static_url_path='')

def get_alignments(alignment_view):
    vtt_file = tempfile.NamedTemporaryFile('w', dir="static/", suffix='.vtt', delete=False)
    vtt_file.write("WEBVTT\n\n")
    annotations = alignment_view.annotations
    # TODO: wanted to use "mmif.get_alignments(AnnotationTypes.TimeFrame, Uri.TOKEN)"
    # but that gave errors so I gave up on it
    token_idx = {a.id:a for a in annotations if str(a.at_type).endswith('Token')}
    timeframe_idx = {a.id:a for a in annotations if str(a.at_type).endswith('TimeFrame')}
    alignments = [a for a in annotations if str(a.at_type).endswith('Alignment')]
    vtt_start = None
    texts = []
    for alignment in alignments:
        start_end_text = build_alignment(alignment, token_idx, timeframe_idx)
        if start_end_text is not None:
            # VTT specifically requires timestamps expressed in miliseconds
            # and must be be in one of these formats 
            # mm:ss.ttt
            # hh:mm:ss.ttt
            # (https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API)
            # ISO format can have up to 6 below the decimal point, on the other hand
            # Assuming here that start and end are in miliseconds
            start, end, text = start_end_text
            if not vtt_start:
                vtt_start = f'{start // 60000:02d}:{start % 60000 // 1000}.{start % 1000:03d}'
            texts.append(text)
            if len(texts) > 8:
                vtt_end = f'{end // 60000:02d}:{end % 60000 // 1000}.{end % 1000:03d}'
                vtt_file.write(f'{vtt_start} --> {vtt_end}\n{" ".join(texts)}\n\n')
                vtt_start = None
                texts = []
    return vtt_file

def build_alignment(alignment, token_idx, timeframe_idx):
    target = alignment.properties['target']
    source = alignment.properties['source']
    timeframe = timeframe_idx.get(source)
    token = token_idx.get(target)
    if timeframe and token:
        start = timeframe.properties['start']
        end = timeframe.properties['end']
        text = token.properties['word']
        return start, end, text

def get_media(mmif):
    # Returns a list of tuples, one for each element in the documents list of
    # the MMIF object, following the order in that list. Each tuple has four
    # elements: document type, document identifier, document path and the HTML
    # visualization.
    media = []
    for document in mmif.documents:
        doc_type = get_document_type_short_form(document)
        doc_path = document.location
        print('>>>', doc_path)
        if doc_type == 'Text':
            html = html_text(doc_path)
        elif doc_type == 'Video':
            fa_views = get_alignment_views(mmif)
            fa_view = fa_views[0] if fa_views else None
            html = html_video(doc_path, fa_view)
        elif doc_type == 'Audio':
            html = html_audio(doc_path)
        elif doc_type == 'Image':
            # TODO: this gives you the last view with BoundingBoxes, should
            # perhaps use get_views_contain() instead, should also select just
            # the bounding boxes and add information from alignments to text
            # documents
            tbox_view = mmif.get_view_contains(str(AnnotationTypes.BoundingBox))
            tbox_annotations = tbox_view.annotations
            # For the boxes we pull some information from the annotation: the
            # identifier, boxType and the (x,y,w,h) coordinates used by the
            # Javascript code that draws the rectangle.
            boxes = []
            for a in tbox_annotations:
                coordinates = a.properties["coordinates"]
                x = coordinates[0][0]
                y = coordinates[0][1]
                w = coordinates[1][0] - x
                h = coordinates[2][1] - y
                box = [a.properties["id"], a.properties["boxType"], [x, y, w, h]]
                boxes.append(box)
            html = html_img(doc_path, boxes)
        media.append((doc_type, document.id, doc_path, html))
    return media


def get_document_type_short_form(document):
    """Returns 'Video', 'Text', 'Audio' or 'Image' from the document type of
    the document."""
    document_type = os.path.split(str(document.at_type))[1]
    return document_type[:-8]


def prep_annotations(mmif):
    """Prepare annotations from the views, and return a list of pairs of tabname
    and tab content. The first tab is alway the full MMIF pretty print."""
    tabs = [("MMIF", "<pre>" + mmif.serialize(pretty=True) + "</pre>"),
            ("Interactive_MMIF", render_interactive_mmif(mmif))]
    # TODO: since this uses the same tab-name this will only show the same
    # stuff; it does a loop but for now we assume there is just one file with
    # alignments (generated by Kaldi)
    for fa_view in get_alignment_views(mmif):
        vtt_file = view_to_vtt(fa_view)
        tabs.append(("WEBVTT", '<pre>' + open(vtt_file).read() + '</pre>'))
    ner_views = get_ner_views(mmif)
    use_id = True if len(ner_views) > 1 else False
    for ner_view in ner_views:
        if not ner_view.annotations:
            continue
        visualization = create_ner_visualization(mmif, ner_view)
        tabname = "Entities-%s" % ner_view.id if use_id else "Entities"
        tabs.append((tabname, visualization))
    # TODO: somewhat hackish
    ocr_views = get_ocr_views(mmif)
    use_id = True if len(ocr_views) > 1 else False
    for ocr_view in ocr_views:
        if not ocr_view.annotations:
            continue
        visualization = prepare_ocr_visualization(mmif, ocr_view)
        tabname = "OCR-%s" % ocr_view.id if use_id else "OCR"
        tabs.append((tabname, visualization))
    return tabs


def get_video_path(mmif):
    media = get_media(mmif)
    for file in media:
        if file[0] == "Video":
            return file[2]
    return None    


def get_document_ids(view, annotation_type):
    metadata = view.metadata.contains.get(annotation_type)
    ids = set([metadata['document']]) if 'document' in metadata else set()
    for annotation in view.annotations:
        if str(annotation.at_type).endswith(str(annotation_type)):
            try:
                ids.add(annotation.properties["document"])
            except KeyError:
                pass
    return list(ids)


def get_alignment_views(mmif):
    """Return alignment views which have at least TextDocument, Token, TimeFrame and
    Alignment annotations."""
    views = []
    needed_types = set(['TextDocument', 'Token', 'TimeFrame', 'Alignment'])
    for view in mmif.views:
        annotation_types = view.metadata.contains.keys()
        annotation_types = [os.path.split(str(at))[-1] for at in annotation_types]
        if needed_types.issubset(annotation_types):
            views.append(view)
    return views



# Remder Media as HTML ------------

def html_video(vpath, vtt_srcview=None):
    print(vpath)
    vpath = url2posix(vpath)
    html = StringIO()
    html.write('<video id="vid" controls>\n')
    html.write(f'    <source src=\"{vpath}\">\n')
    if vtt_srcview is not None:
        vtt_path = view_to_vtt(vtt_srcview)
        # use only basename because "static" directory is mapped to '' route by
        # `static_url_path` param
        src = os.path.basename(vtt_path)
        html.write(f'    <track kind="subtitles" srclang="en" src="{src}" default>\n')
    html.write("</video>\n")
    return html.getvalue()


def html_text(tpath):
    """Return the conent of the text document, but with some HTML tags added."""
    if not os.path.isfile(tpath):
        # This is to fix a problem when running this from a local machine where
        # /data/text may not be available (it always is available from the
        # container). The same problem occurs in displacy/__init__.py.
        if tpath.startswith('file:///'):
            tpath = tpath[8:]
        else:
            # this should not happen anymore, but keeping it anyway
            tpath = tpath[1:]
        tpath = os.path.join(app.root_path, 'static', tpath)
    with open(tpath) as t_file:
        #return f"<pre width=\"100%\">\n{t_file.read()}\n</pre>"
        content = t_file.read().replace("\n", "<br/>\n")
        return f"{content}\n"


def html_img(ipath, boxes=None, id="imgCanvas"):
    ipath = url2posix(ipath)
    boxes = [] if boxes is None else boxes
    # t = Template(open('templates/image.html').read())
    return render_template('image.html', filename=ipath, boxes=boxes, id=id)


def html_audio(apath):
    apath = url2posix(apath)
    return f"<audio controls src={apath}></audio>"


def url2posix(path):
    """For the visualizer we often want a POSIX path and not a URL so we strip off
    the protocol if there is one."""
    if path.startswith('file:///'):
        path = path[7:]
    return path

# Interactive MMIF Tab -----------

def render_interactive_mmif(mmif):
    return render_template('interactive.html', mmif=mmif)

# NER Tools ----------------------

def get_ner_views(mmif):
    return [v for v in mmif.views if Uri.NE in v.metadata.contains]

def view_to_vtt(alignment_view):
    """Write alignments to a file in VTT style and return the filename."""
    vtt_file = get_alignments(alignment_view)
    return os.sep.join(vtt_file.name.split(os.sep)[-2:])

def create_ner_visualization(mmif, view):
    metadata = view.metadata.contains.get(Uri.NE)
    try:
        # all the view's named entities refer to the same text document (kaldi)
        document_ids = get_document_ids(view, Uri.NE)
        return displacy.visualize_ner(mmif, view, document_ids[0], app.root_path)
    except KeyError:
        # the view's entities refer to more than one text document (tessearct)
        pass

# OCR Tools ----------------------

def prepare_ocr_visualization(mmif, view):
    """ Visualize OCR by extracting image frames with BoundingBoxes from video"""
    frames, text_docs, alignments = {}, {}, {}
    for anno in view.annotations:
        try:
            if str(anno.at_type).endswith('BoundingBox'):
                frames = add_bounding_box(anno, frames)

            elif str(anno.at_type).endswith('TextDocument'):
                t = anno.properties["text_value"]
                if t:
                    text_id = anno.properties["id"]
                    # Format string so it is JSON-readable
                    text_docs[text_id] = re.sub(r'[^\w]', '', t)

            elif str(anno.at_type).endswith('Alignment'):
                source = anno.properties["source"]
                target = anno.properties["target"]
                alignments[source] = target

        except Exception as e:
            print(f"Unexpected error of type {type(e)}: {e}")
            pass

    vid_path = get_video_path(mmif)
    cv2_vid = cv2.VideoCapture(vid_path)
    fps = cv2_vid.get(cv2.CAP_PROP_FPS)
    frames_list = [(k, v) for k, v in frames.items()]
    frames_list = align_annotations(frames_list, alignments, text_docs, fps)
    frames_pages = paginate(frames_list)
    return render_ocr(vid_path, frames_pages, alignments, text_docs, 0)


def add_bounding_box(anno, frames):
    frame_num = anno.properties["frame"]
    box_id = anno.properties["id"]
    boxType = anno.properties["boxType"]
    coordinates = anno.properties["coordinates"]
    x = coordinates[0][0]
    y = coordinates[0][1]
    w = coordinates[3][0] - x
    h = coordinates[3][1] - y
    box = [box_id, boxType, [x, y, w, h]]
    if frame_num in frames.keys():
        frames[frame_num]["boxes"].append(box)
        frames[frame_num]["bb_ids"].append(box_id)
    else:
        frames[frame_num] = {"boxes": [box], "text": [], "bb_ids": [box_id], "timestamp": None, "secs": None, "repeat": False}
    return frames


def align_annotations(frames_list, alignments, text_docs, fps):
    prev_frame = None
    for frame_num, frame in frames_list:
        if fps:
            secs = int(frame_num/fps)
            frame["timestamp"] = datetime.timedelta(seconds=secs)
            frame["secs"] = secs
        for box_id in frame["bb_ids"]:
            text_id = alignments[box_id]
            frame["text"].append(text_docs[text_id])
        if is_duplicate_ocr_frame(frame, prev_frame):
            frame["repeat"] = True
        prev_frame = frame
    return frames_list

def paginate(frames_list):
    pages = [[]]
    n_frames_on_page = 0
    for frame_num, frame in frames_list:
        if n_frames_on_page >= 4 and not frame["repeat"]:
            pages.append([])
            n_frames_on_page = 0

        pages[-1].append((frame_num, frame))

        if not frame["repeat"]:
            n_frames_on_page += 1

    return pages

def render_ocr(vid_path, frames_pages, alignments, text_docs, page_number):
    """Iterate through frames and display the contents/alignments."""
    # Path for storing temporary images generated by cv2
    tmp_path = '/app/static/tmp'
    if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)

    cv2_vid = cv2.VideoCapture(vid_path)
    for frame_num, frame in frames_pages[page_number]:
        cv2_vid.set(1, frame_num)
        _, frame_cap = cv2_vid.read()
        with tempfile.NamedTemporaryFile(
            prefix="/app/static/tmp/", suffix=".jpg", delete=False) as tf:
            cv2.imwrite(tf.name, frame_cap)
            # "id" is just the name of the temp image file
            frame["id"] = tf.name[12:]            

    return render_template('ocr.html', 
                           vid_path=vid_path, 
                           frames_pages=frames_pages, 
                           alignments=alignments, 
                           text_docs=text_docs, 
                           page_number=page_number)


def is_duplicate_ocr_frame(frame, prev_frame):
    if prev_frame:
        # Check Boundingbox distances
        rounded_prev = round_boxes(prev_frame["boxes"])
        for box in round_boxes(frame["boxes"]):
            if box in rounded_prev and frame["secs"]-prev_frame["secs"] < 5:
                return True
    return False

def round_boxes(boxes):
    # To account for jittery bounding boxes in OCR annotations
    rounded_boxes = []
    for box in boxes:
        rounded_box = []
        for coord in box[2]:
            rounded_box.append(round(coord/10)*10)
        rounded_boxes.append(rounded_box)
    return rounded_boxes

def get_ocr_views(mmif):
    """Return OCR views, which have TextDocument and Alignment annotations, but no
    other annotations."""
    views = []
    # TODO: not sure why we use the full URL
    needed_types = set([
        "http://mmif.clams.ai/0.4.0/vocabulary/TextDocument",
        "http://mmif.clams.ai/0.4.0/vocabulary/BoundingBox",
        "http://mmif.clams.ai/0.4.0/vocabulary/Alignment" ])
    for view in mmif.views:
        annotation_types = view.metadata.contains.keys()
        if needed_types.issubset(annotation_types) and len(annotation_types) == 3:
            views.append(view)
    return views

def change_page(frames, lower_n, upper_n, step, direction):
    if direction == FORWARD:
        lower = upper_n + 1
    else:
        lower = lower_n - step
        while frames[lower][1]["repeat"]:
            lower -= 1
    upper = lower + step
    while upper < len(frames)-1 and frames[upper+1][1]["repeat"]:
        upper += 1
    return lower, upper