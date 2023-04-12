import os
import cv2
from io import StringIO
import displacy
import tempfile
import re
import json

from flask import Flask, render_template
from mmif.vocabulary import AnnotationTypes
from lapps.discriminators import Uri
from iiif_utils import generate_iiif_manifest
from ocr import *


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
    manifest_filename = generate_iiif_manifest(mmif)
    man = os.path.basename(manifest_filename)
    temp = render_template("uv_player.html", manifest=man)
    media.append(('UV', "", "", temp))
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
    # organize_alignments(mmif)
    return render_template('interactive.html', mmif=mmif)

# def organize_alignments(mmif):
#     """Organize all alignments so they are directly adjacent to the elements they align"""
#     for view in mmif.views:
#         if any([str(at_type).endswith('Alignment') for at_type in view.metadata.contains]):
#             organize(view.annotations)

# def organize(annotations):
#     new_anno_list = []
#     for annotation in annotations:
#         new_anno_list.append(annotation)
#     return new_anno_list

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
                    text_docs[text_id] = re.sub(r'([\\\/\|\"\'])', r'\1 ', t)

            elif str(anno.at_type).endswith('Alignment'):
                source = anno.properties["source"]
                target = anno.properties["target"]
                alignments[source] = target

        except Exception as e:
            print(f"Unexpected error of type {type(e)}: {e}")
            pass

    # Generate pages (necessary to reduce IO cost) and render
    vid_path = get_video_path(mmif)
    cv2_vid = cv2.VideoCapture(vid_path)
    fps = cv2_vid.get(cv2.CAP_PROP_FPS)
    frames_list = [(k, v) for k, v in frames.items()]
    frames_list = align_annotations(frames_list, alignments, text_docs, fps)
    frames_pages = paginate(frames_list)
    return render_ocr(vid_path, frames_pages, 0)