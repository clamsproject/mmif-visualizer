import os
import sys
import json
import secrets

from io import StringIO
from string import Template

import displacy
import requests
import tempfile

from flask import Flask, request, render_template, flash, redirect
from werkzeug.utils import secure_filename

from mmif.serialize import Mmif, View
from mmif.vocabulary import AnnotationTypes
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri


# these two static folder-related params are important, do not remove
app = Flask(__name__, static_folder='static', static_url_path='')

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # NOTE. Uses of flash() originally gaven a RuntimeError (The session is
    # unavailable because no secret key was set). This was solved in the
    # __main__ block by setting a key.
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('WARNING: post request has no file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('WARNING: no file was selected')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join('temp', filename))
            with open("temp/" + filename) as fh:
                mmif_str = fh.read()
                return render_mmif(mmif_str)
    return render_template('upload.html')


def render_mmif(mmif_str):
    mmif = Mmif(mmif_str)
    media = get_media(mmif)
    annotations = prep_annotations(mmif)
    return render_template('player.html',
                           mmif=mmif, media=media, annotations=annotations)


def view_to_vtt(alignment_view):
    """Write alignments to a file in VTT style and return the filename."""
    vtt_file = get_alignments(alignment_view)
    return os.sep.join(vtt_file.name.split(os.sep)[-2:])


def get_alignments(alignment_view):
    vtt_file = tempfile.NamedTemporaryFile('w', dir="static/", suffix='.vtt', delete=False)
    vtt_file.write("WEBVTT\n\n")
    annotations = alignment_view.annotations
    # TODO: wanted to use "mmif.get_alignments(AnnotationTypes.TimeFrame, Uri.TOKEN)"
    # but that gave errors so I gave up on it
    token_idx = {a.id:a for a in annotations if a.at_type.endswith('Token')}
    timeframe_idx = {a.id:a for a in annotations if a.at_type.endswith('TimeFrame')}
    alignments = [a for a in annotations if a.at_type.endswith('Alignment')]
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


def html_video(vpath, vtt_srcview=None):
    html = StringIO()
    html.write("<video controls>\n")
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
        tpath = os.path.join(app.root_path, 'static', tpath[1:])
    with open(tpath) as t_file:
        #return f"<pre width=\"100%\">\n{t_file.read()}\n</pre>"
        content = t_file.read().replace("\n", "<br/>\n")
        return f"{content}\n"


def html_img(ipath, boxes=None):
    boxes = [] if boxes is None else boxes
    t = Template(open('templates/image.html').read())
    return t.substitute(filename=ipath, boxes=boxes)


def html_audio(apath):
    return f"<audio controls src={apath}></audio>"


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
            tbox_view = mmif.get_view_contains(AnnotationTypes.BoundingBox)
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
    document_type = os.path.split(document.at_type)[1]
    return document_type[:-8]


def prep_annotations(mmif):
    """Prepare annotations from the views, and return a list of pairs of tabname
    and tab content. The first tab is alway the full MMIF pretty print."""
    tabs = [("MMIF", "<pre>" + mmif.serialize(pretty=True) + "</pre>")]
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
        visualization = create_ocr_visualization(mmif, ocr_view)
        tabname = "OCR-%s" % ocr_view.id if use_id else "OCR"
        tabs.append((tabname, visualization))
    return tabs


def create_ner_visualization(mmif, view):
    metadata = view.metadata.contains.get(Uri.NE)
    try:
        # all the view's named entities refer to the same text document (kaldi)
        document_ids = get_document_ids(view, Uri.NE)
        return displacy.visualize_ner(mmif, view, document_ids[0], app.root_path)
    except KeyError:
        # the view's entities refer to more than one text document (tessearct)
        pass


def create_ocr_visualization(mmif, view):
    # TODO: the text boxes had no timePoint so I could not create a VTT
    # TODO: no app in the metadata
    text = '<pre>'
    for anno in view.annotations:
        try:
            if anno.at_type.endswith('TextDocument'):
                # TODO: this is a hack because the text documents do not have a text
                # field, instead they have an @value field
                t = str(anno.properties).split('"id":')
                t = anno.properties['_value']
                t = ' '.join(t.split()).strip()
                if t:
                    text += t + '\n'
        except:
            pass
    return text + '</pre>'


def get_document_ids(view, annotation_type):
    metadata = view.metadata.contains.get(annotation_type)
    ids = set([metadata['document']]) if 'document' in metadata else set()
    for annotation in view.annotations:
        if annotation.at_type.endswith(annotation_type):
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
        annotation_types = [os.path.split(at)[-1] for at in annotation_types]
        if needed_types.issubset(annotation_types):
            views.append(view)
    return views


def get_ocr_views(mmif):
    """Return OCR views, which have TextDocument and Alignment annotations, but no
    other annotations."""
    views = []
    # TODO: not sure why we use the full URL
    needed_types = set([
        "http://mmif.clams.ai/0.2.1/vocabulary/TextDocument",
        "http://mmif.clams.ai/0.2.1/vocabulary/Alignment" ])
    for view in mmif.views:
        annotation_types = view.metadata.contains.keys()
        if needed_types.issubset(annotation_types) and len(annotation_types) == 2:
            views.append(view)
    return views


def get_ner_views(mmif):
    return [v for v in mmif.views if Uri.NE in v.metadata.contains]


# Not sure what this was for, it had a route /display, but that did not work
# def display_file():
#    mmif_str = requests.get(request.args["file"]).text
#    return display_mmif(mmif_str)


if __name__ == '__main__':

    # to avoid runtime errors for missing keys when using flash()
    alphabet = 'abcdefghijklmnopqrstuvwxyz1234567890'
    app.secret_key = ''.join(secrets.choice(alphabet) for i in range(36))

    port = 5000
    if len(sys.argv) > 2 and sys.argv[1] == '-p':
        port = int(sys.argv[2])
    app.run(port=port, host='0.0.0.0', debug=True)
