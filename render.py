import os
import pathlib
import shutil
import tempfile
import threading
import time
from io import StringIO
from collections import Counter
from flask import render_template, current_app

from mmif import DocumentTypes
from mmif.serialize.annotation import Text
from mmif.vocabulary import AnnotationTypes
from lapps.discriminators import Uri
import displacy

from helpers import *

import cache

"""
Methods to render MMIF documents and their annotations in various formats.
"""

# -- Documents --

def render_documents(mmif, viz_id):
    """
    Returns HTML Tab representation of all documents in the MMIF object.
    """
    tabs = []
    for document in mmif.documents:
        doc_path = get_doc_path(document)
        if document.at_type == DocumentTypes.TextDocument:
            html_tab = render_text(doc_path)
        elif document.at_type == DocumentTypes.ImageDocument:
            html_tab = render_image(doc_path)
        elif document.at_type == DocumentTypes.AudioDocument:
            html_tab = render_audio(doc_path)
        elif document.at_type == DocumentTypes.VideoDocument:
            html_tab = render_video(doc_path, mmif, viz_id)

        tabs.append({"id": document.id, 
                     "tab_name": document.at_type.shortname, 
                     "html": html_tab})
    return tabs

def render_text(text_path):
    """Return the content of the text document, but with some HTML tags added."""
    if not os.path.isfile(text_path):
        raise FileNotFoundError(f"File not found: {text_path}")
    with open(text_path) as t_file:
        content = t_file.read().replace("\n", "<br/>\n")
        return f"{content}\n"

def render_image(img_path):
    return ""

def render_audio(audio_path):
    return ""

def render_video(vid_path, mmif, viz_id):
    vid_path = url2posix(vid_path)
    html = StringIO()
    html.write('<video id="vid" controls crossorigin="anonymous" >\n')
    html.write(f'    <source src=\"{vid_path}\">\n')
    for view in mmif.views:
        if get_abstract_view_type(view) == "ASR":
            vtt_path = get_vtt_file(view, viz_id)
            rel_vtt_path = vtt_path[(len("/tmp/") + len(current_app.static_folder)):]
            html.write(f'    <track kind="captions" srclang="en" src="/{rel_vtt_path}" label="transcript" default/>\n')
    html.write("</video>\n")
    return html.getvalue()

# -- Annotations --

def render_annotations(mmif, viz_id):
    """
    Returns HTML Tab representation of all annotations in the MMIF object.
    """
    tabs = []
    # These tabs should always be present
    tabs.append({"id": "info", "tab_name": "Info", "html": render_info(mmif)})
    tabs.append({"id": "annotations", "tab_name": "Annotations", "html": render_annotation_table(mmif)})
    tabs.append({"id": "tree", "tab_name": "Tree", "html": render_jstree(mmif)})
    # These tabs are optional
    for view in mmif.views:
        abstract_view_type = get_abstract_view_type(view)
        app_shortname = view.metadata.app.split("/")[-2]
        if abstract_view_type == "NER":
            tabs.append({"id": view.id, "tab_name": f"{app_shortname}-{view.id}", "html": render_ner(mmif, view)})
        elif abstract_view_type == "ASR":
            tabs.append({"id": view.id, "tab_name": f"{app_shortname}-{view.id}", "html": render_asr_vtt(view, viz_id)})
    return tabs

def render_info(mmif):
    s = StringIO('Howdy')
    s.write("<pre>")
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
    s.write("</pre>")
    return s.getvalue()


def render_annotation_table(mmif):
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

def render_jstree(mmif):
    return render_template('interactive.html', mmif=mmif, aligned_views=[])

def render_asr_vtt(view, viz_id):
    vtt_filename = get_vtt_file(view, viz_id)
    with open(vtt_filename) as vtt_file:
        vtt_content = vtt_file.read()
    return f"<pre>{vtt_content}</pre>"

def render_ner(mmif, view):
    metadata = view.metadata.contains.get(Uri.NE)
    ner_document = metadata.get('document')
    return displacy.visualize_ner(mmif, view, ner_document, current_app.root_path)

def render_ocr():
    pass