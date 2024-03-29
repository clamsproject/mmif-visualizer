from collections import Counter
from datetime import timedelta
from io import StringIO

from flask import Flask, url_for
from lapps.discriminators import Uri
from mmif import DocumentTypes
from mmif.serialize.annotation import Text, Document
from mmif.vocabulary import AnnotationTypes

import displacy
import iiif_utils
from ocr import *

# Get Properties from MMIF file ---

# these two static folder-related params are important, do not remove
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'your_secret_key_here'


def asr_alignments_to_vtt(alignment_view, viz_id):
    vtt_filename = cache.get_cache_root() / viz_id / f"{alignment_view.id.replace(':', '-')}.vtt" 
    if vtt_filename.exists():
        return str(vtt_filename)
    vtt_file = open(vtt_filename, 'w')
    vtt_file.write("WEBVTT\n\n")
    annotations = alignment_view.annotations
    timeframe_at_type = [at_type for at_type in alignment_view.metadata.contains if at_type.shortname == "TimeFrame"][0]
    timeunit = alignment_view.metadata.contains[timeframe_at_type]["timeUnit"]
    # TODO: wanted to use "mmif.get_alignments(AnnotationTypes.TimeFrame, Uri.TOKEN)"
    # but that gave errors so I gave up on it
    token_idx = {a.id: a for a in annotations if a.at_type.shortname == "Token"}
    timeframe_idx = {a.id: a for a in annotations if a.at_type.shortname == "TimeFrame"}
    alignments = [a for a in annotations if a.at_type.shortname == "Alignment"]
    vtt_start = None
    texts = []
    for alignment in alignments:
        start_end_text = build_alignment(alignment, token_idx, timeframe_idx)
        if start_end_text is not None:
            # VTT specifically requires timestamps expressed in miliseconds and
            # must be be in one of these formats: mm:ss.ttt or hh:mm:ss.ttt
            # (https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API)
            # ISO format can have up to 6 below the decimal point, on the other hand
            # Assuming here that start and end are in miliseconds
            start, end, text = start_end_text
            start_kwarg, end_kwarg = {timeunit: float(start)}, {timeunit: float(end)}
            start, end = timedelta(**start_kwarg), timedelta(**end_kwarg)
            s_mins, s_secs = divmod(start.seconds, 60)
            e_mins, e_secs = divmod(end.seconds, 60)
            if not vtt_start:
                vtt_start = f'{s_mins:02d}:{s_secs:02d}.{((s_secs - int(s_secs)) * 1000):03d}'
            texts.append(text)
            if len(texts) > 8:
                vtt_end = f'{e_mins:02d}:{e_secs:02d}.{((e_secs - int(e_secs)) * 1000):03d}'
                vtt_file.write(f'{vtt_start} --> {vtt_end}\n{" ".join(texts)}\n\n')
                vtt_start = None
                texts = []
    return vtt_file.name


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


def get_src_media_symlink_basename(doc: Document):
    doc_path = doc.location_path()
    return f"{doc.id}.{doc_path.split('.')[-1]}"


def get_symlink_relurl(viz_id, symlink_fname):
    static_folder = pathlib.Path(app.static_folder)
    symlink_path = pathlib.Path(cache._CACHE_DIR_SUFFIX) / viz_id / symlink_fname
    return static_folder / symlink_path


def symlink_to_static(viz_id, original_path, symlink_fname) -> str:
    static_folder = pathlib.Path(app.static_folder)
    symlink_path = pathlib.Path(cache._CACHE_DIR_SUFFIX) / viz_id / symlink_fname
    app.logger.debug(f"Symlinking {original_path} to {symlink_path}")
    try:
        os.symlink(original_path, static_folder / symlink_path)
    except Exception as e:
        app.logger.error(f"SOME ERROR when symlinking: {str(e)}")
    app.logger.debug(f"{original_path} is symlinked to {symlink_path}")
    symlink_rel_path = url_for('static', filename=symlink_path)
    app.logger.debug(f"and exposable as {symlink_rel_path}")
    return symlink_rel_path


def documents_to_htmls(mmif, viz_id):
    """
    Returns a list of tuples, one for each element in the documents list of
    the MMIF object, following the order in that list. Each tuple has four
    elements: document type, document identifier, document path and the HTML
    visualization.
    """
    htmlized = []
    for document in mmif.documents:
        doc_path = document.location_path()
        app.logger.debug(f"MMIF on AV asset: {doc_path}")
        linked = symlink_to_static(viz_id, doc_path, get_src_media_symlink_basename(document))
        if document.at_type == DocumentTypes.TextDocument:
            html = html_text(linked)
        elif document.at_type == DocumentTypes.VideoDocument:
            fa_views = get_alignment_views(mmif)
            fa_view = fa_views[0] if fa_views else None
            html = html_video(viz_id, linked, fa_view)
        elif document.at_type == DocumentTypes.AudioDocument:
            html = html_audio(linked)
        elif document.at_type == DocumentTypes.ImageDocument:
            boxes = get_boxes(mmif)
            html = html_img(linked, boxes)
        htmlized.append((document.at_type.shortname, document.id, doc_path, html))
    manifest_filename = iiif_utils.generate_iiif_manifest(mmif, viz_id)
    app.logger.debug(f"Generated IIIF manifest: {manifest_filename}")
    man = os.path.basename(manifest_filename)
    app.logger.debug(f"Manifest filename: {man}")
    symlink_to_static(viz_id, manifest_filename, man)
    app.logger.debug(f"Symlinked IIIF manifest: {None}")
    temp = render_template("uv_player.html", manifest=man, mmif_id=viz_id)
    # TODO (krim @ 2024-03-12): Turning off IIIF added to the HTML page since
    # 1. current IIIF manifest conversion is based on old version of manifest API, and quite brittle
    # 2. the conversion code at the moment can only convert TimeFrame annotation to "jump-able" IIIF canvases, 
    # but the case is already covered by `Thumbnails` tab (look for usage of `pre-ocr.html` template)
    # htmlized.append(('UV', "", "", temp))
    return htmlized


def get_boxes(mmif):
    # TODO: this gives you the last view with BoundingBoxes, should
    # perhaps use get_views_contain() instead, should also select just
    # the bounding boxes and add information from alignments to text
    # documents.
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
    return boxes


def prep_annotations(mmif, viz_id):
    """Prepare annotations from the views, and return a list of pairs of tabname
    and tab content. The first tab is alway the full MMIF pretty print."""
    tabs = []
    tabs.append(("Info", "<pre>" + create_info(mmif) + "</pre>"))
    app.logger.debug(f"Prepared INFO Tab: {tabs[-1][0]}")
    # tabs.append(("MMIF", "<pre>" + mmif.serialize(pretty=True) + "</pre>"))
    # app.logger.debug(f"Prepared RAW Tab: {tabs[-1][0]}")
    tabs.append(("Annotations", create_annotation_tables(mmif)))
    app.logger.debug(f"Prepared SUMMARY Tab: {tabs[-1][0]}")
    tabs.append(("Tree", render_interactive_mmif(mmif)))
    app.logger.debug(f"Prepared JSTREE Tab: {tabs[-1][0]}")
    # TODO: since this uses the same tab-name this will only show the same
    # stuff; it does a loop but for now we assume there is just one file with
    # alignments (generated by Kaldi)
    for fa_view in get_alignment_views(mmif):
        vtt_file = asr_alignments_to_vtt(fa_view, viz_id)
        tabs.append(("WebVTT", '<pre>' + open(vtt_file).read() + '</pre>'))
        app.logger.debug(f"Prepared a VTT Tab: {tabs[-1][0]}")
    ner_views = get_ner_views(mmif)
    use_id = True if len(ner_views) > 1 else False
    for ner_view in ner_views:
        if not ner_view.annotations:
            continue
        visualization = create_ner_visualization(mmif, ner_view)
        tabname = "Entities-%s" % ner_view.id if use_id else "Entities"
        tabs.append((tabname, visualization))
        app.logger.debug(f"Prepared a displaCy Tab: {tabs[-1][0]}")
    # TODO: somewhat hackish
    ocr_views = get_ocr_views(mmif)
    use_id = True if len(ocr_views) > 1 else False
    for ocr_view in ocr_views:
        if not ocr_view.annotations:
            continue
        tabname = "Thumbnails-%s" % ocr_view.id
        visualization = render_template("pre-ocr.html", view_id=ocr_view.id, tabname=tabname, mmif_id=viz_id)
        tabs.append((tabname, visualization))
        app.logger.debug(f"Prepared a Thumbnails Tab: {tabs[-1][0]}")
    return tabs


def create_info(mmif):
    s = StringIO('Howdy')
    for document in mmif.documents:
        at_type = document.at_type.shortname
        location = document.location
        s.write("%s  %s\n" % (at_type, location))
    s.write('\n')
    for view in mmif.views:
        app = view.metadata.app
        status = get_status(view)
        s.write('%s  %s  %s  %d\n' % (view.id, app, status, len(view.annotations)))
        if len(view.annotations) > 0:
            s.write('\n')
            types = Counter([a.at_type.shortname
                             for a in view.annotations])
            for attype, count in types.items():
                s.write('    %4d %s\n' % (count, attype))
        s.write('\n')
    return s.getvalue()


def create_annotation_tables(mmif):
    s = StringIO('Howdy')
    for view in mmif.views:
        status = get_status(view)
        s.write('<p><b>%s  %s</b>  %s  %d annotations</p>\n'
                % (view.id, view.metadata.app, status, len(view.annotations)))
        s.write("<blockquote>\n")
        s.write("<table cellspacing=0 cellpadding=5 border=1>\n")
        limit_len = lambda str: str[:500] + "  . . .  }" if len(str) > 500 else str
        for annotation in view.annotations:
            s.write('  <tr>\n')
            s.write('    <td>%s</td>\n' % annotation.id)
            s.write('    <td>%s</td>\n' % annotation.at_type.shortname)
            s.write('    <td>%s</td>\n' % limit_len(get_properties(annotation)))
            s.write('  </tr>\n')
        s.write("</table>\n")
        s.write("</blockquote>\n")
    return s.getvalue()


def get_document_ids(view, annotation_type):
    metadata = view.metadata.contains.get(annotation_type)
    ids = set([metadata['document']]) if 'document' in metadata else set()
    for annotation in view.annotations:
        if annotation.at_type.shortname == str(annotation_type):
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
        annotation_types = [at.shortname for at in annotation_types]
        if needed_types.issubset(annotation_types):
            views.append(view)
    return views


# Render documents as HTML ------------

def html_video(viz_id, vpath, vtt_srcview=None):
    vpath = url2posix(vpath)
    html = StringIO()
    html.write('<video id="vid" controls crossorigin="anonymous" >\n')
    html.write(f'    <source src=\"{vpath}\">\n')
    if vtt_srcview is not None:
        vtt_path = asr_alignments_to_vtt(vtt_srcview, viz_id)
        rel_vtt_path = str(vtt_path)[len(app.static_folder):]
        app.logger.debug(f"VTT path: {vtt_path}")
        html.write(f'    <track kind="captions" srclang="en" src="{rel_vtt_path}" label="transcript" default/>\n')
    html.write("</video>\n")
    return html.getvalue()


def html_text(tpath):
    """Return the content of the text document, but with some HTML tags added."""
    if not os.path.isfile(tpath):
        raise FileNotFoundError(f"File not found: {tpath}")
    with open(tpath) as t_file:
        content = t_file.read().replace("\n", "<br/>\n")
        return f"{content}\n"


def html_img(ipath, boxes=None, id="imgCanvas"):
    ipath = url2posix(ipath)
    boxes = [] if boxes is None else boxes
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
    return render_template('interactive.html', mmif=mmif, aligned_views=get_aligned_views(mmif))


# Functions for checking if view can be rendered with alignment highlighting
def get_aligned_views(mmif):
    """Return list of properly aligned views (for tree display)"""
    aligned_views = []
    for view in mmif.views:
        if any([at_type.shortname == "Alignment" for at_type in view.metadata.contains]):
            if check_view_alignment(view.annotations) == True:
                aligned_views.append(view.id)
    return aligned_views


def check_view_alignment(annotations):
    anno_stack = []
    for annotation in annotations:
        if annotation.at_type.shortname == "Alignment":
            anno_stack.insert(0, annotation.properties)
        else:
            anno_stack.append(annotation.id)
        if len(anno_stack) == 3:
            if type(anno_stack[0]) == str or not (
                    anno_stack[0]["source"] in anno_stack and anno_stack[0]["target"] in anno_stack):
                return False
            anno_stack = []
    return True


# NER Tools ----------------------

def get_ner_views(mmif):
    return [v for v in mmif.views if Uri.NE in v.metadata.contains]


def create_ner_visualization(mmif, view):
    metadata = view.metadata.contains.get(Uri.NE)
    try:
        # all the view's named entities refer to the same text document (kaldi)
        document_ids = get_document_ids(view, Uri.NE)
        return displacy.visualize_ner(mmif, view, document_ids[0], app.root_path)
    except KeyError as e:
        # the view's entities refer to more than one text document (tessearct)
        pass


def get_status(view):
    return 'ERROR' if 'message' in view.metadata.error else 'OKAY'


def get_properties(annotation):
    props = annotation.properties._serialize()
    props.pop('id')
    props_list = []
    for prop in sorted(props):
        val = props[prop]
        if type(val) == Text:
            val = val.value
        props_list.append("%s=%s" % (prop, val))
    return '{ %s }' % ', '.join(props_list)


# OCR Tools ----------------------

def prepare_ocr_visualization(mmif, view, mmif_id):
    """ Visualize OCR by extracting image frames with BoundingBoxes from video"""
    # frames, text_docs, alignments = {}, {}, {}
    vid_path = mmif.get_documents_by_type(DocumentTypes.VideoDocument)[0].location_path()
    cv2_vid = cv2.VideoCapture(vid_path)
    fps = cv2_vid.get(cv2.CAP_PROP_FPS)

    ocr_frames = get_ocr_frames(view, mmif, fps)

    # Generate pages (necessary to reduce IO cost) and render
    frames_list = [(k, vars(v)) for k, v in ocr_frames.items()]
    frames_list = find_duplicates(frames_list, cv2_vid)
    frames_pages = paginate(frames_list)
    # Save page list as temp file
    save_json(frames_pages, view.id, mmif_id)
    return render_ocr(mmif_id, vid_path, view.id, 0)
