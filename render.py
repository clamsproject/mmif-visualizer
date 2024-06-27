import os
import pathlib
from io import StringIO
from collections import Counter
from flask import render_template, current_app
import re

from mmif import DocumentTypes
from lapps.discriminators import Uri
import displacy
import traceback

from utils import get_status, get_properties, get_abstract_view_type, url2posix, get_vtt_file
from ocr import prepare_ocr, make_image_directory, is_duplicate_image
import cv2
import json
import tempfile

import cache

"""
Methods to render MMIF documents and their annotations in various formats.
"""

# -- Render methods --


def render_documents(mmif, viz_id):
    """
    Returns HTML Tab representation of all documents in the MMIF object.
    """
    tabs = []
    for document in mmif.documents:
        if document.at_type == DocumentTypes.TextDocument:
            tabs.append(TextTab(document, viz_id))
        elif document.at_type == DocumentTypes.ImageDocument:
            tabs.append(ImageTab(document, viz_id))
        elif document.at_type == DocumentTypes.AudioDocument:
            tabs.append(AudioTab(document, viz_id))
        elif document.at_type == DocumentTypes.VideoDocument:
            tabs.append(VideoTab(document, mmif, viz_id))

    return tabs


def render_annotations(mmif, viz_id):
    """
    Returns HTML Tab representation of all annotations in the MMIF object.
    """
    tabs = []
    # These tabs should always be present
    tabs.append(InfoTab(mmif))
    tabs.append(AnnotationTableTab(mmif))
    tabs.append(JSTreeTab(mmif))
    # These tabs are optional
    for view in mmif.views:
        abstract_view_type = get_abstract_view_type(view, mmif)
        if abstract_view_type == "NER":
            tabs.append(NERTab(mmif, view))
        elif abstract_view_type == "ASR":
            tabs.append(VTTTab(mmif, view, viz_id))
        elif abstract_view_type == "OCR":
            tabs.append(OCRTab(mmif, view, viz_id))

    return tabs


# -- Base Tab Class --

class DocumentTab():
    def __init__(self, document, viz_id):
        self.id = document.id
        self.tab_name = document.at_type.shortname
        self.viz_id = viz_id

        try:
            # Add symbolic link to document to static folder, so it can be accessed
            # by the browser.
            self.doc_path = document.location_path()
            self.doc_symlink_path = pathlib.Path(
                current_app.static_folder) / cache._CACHE_DIR_SUFFIX / viz_id / (f"{document.id}.{self.doc_path.split('.')[-1]}")
            os.symlink(self.doc_path, self.doc_symlink_path)
            self.doc_symlink_rel_path = '/' + \
                self.doc_symlink_path.relative_to(
                    current_app.static_folder).as_posix()

            self.html = self.render()

        except Exception as e:
            self.html = f"Error rendering document: <br><br> <pre>{traceback.format_exc()}</pre>"

    def __str__(self):
        return f"Tab: {self.tab_name} ({self.id})"


class AnnotationTab():
    def __init__(self, mmif, view=None):
        self.mmif = mmif
        # Some AnnotationTab sub-classes don't refer to a specific view, and so
        # they specify their own ids and tab names. For ones that do refer to
        # a specific view, we set the ids/tab names based on view properties.
        if view:
            self.view = view
            # Workaround to deal with the fact that some apps have a version number
            # in the URL
            app_url = view.metadata.app if re.search(
                r"\/v\d+\.?\d?$", view.metadata.app) else view.metadata.app + "/v1"
            app_shortname = app_url.split("/")[-2]

            self.id = view.id
            self.tab_name = f"{app_shortname}-{view.id}"
        try:
            self.html = self.render()
        except Exception as e:
            self.html = f"Error rendering view: <br><br> <pre>{traceback.format_exc()}</pre>"


# -- Document Classes --

class TextTab(DocumentTab):
    def __init__(self, document, viz_id):
        super().__init__(document, viz_id)

    def render(self):
        with open(self.doc_path) as t_file:
            content = t_file.read().replace("\n", "<br/>\n")
            return f"{content}\n"


class ImageTab(DocumentTab):
    def __init__(self, document, viz_id):
        super().__init__(document, viz_id)

    def render(self):
        img_path = url2posix(self.doc_path)
        html = StringIO()
        html.write(
            f'<img src=\"{img_path}\" alt="Image" style="max-width: 100%">\n')
        return html.getvalue()


class AudioTab(DocumentTab):
    def __init__(self, document, viz_id):
        super().__init__(document, viz_id)

    def render(self):
        audio_path = url2posix(self.doc_symlink_rel_path)
        html = StringIO()
        html.write('<audio id="audioplayer" controls crossorigin="anonymous">\n')
        html.write(f'    <source src=\"{audio_path}\">\n')
        html.write("</audio>\n")
        return html.getvalue()


class VideoTab(DocumentTab):
    def __init__(self, document, mmif, viz_id):
        # VideoTab needs access to the MMIF object to get the VTT file
        self.mmif = mmif
        super().__init__(document, viz_id)

    def render(self):
        vid_path = url2posix(self.doc_symlink_rel_path)
        html = StringIO()
        html.write('<video id="vid" controls crossorigin="anonymous" >\n')
        html.write(f'    <source src=\"{vid_path}\">\n')
        for view in self.mmif.views:
            if get_abstract_view_type(view, self.mmif) == "ASR":
                vtt_path = get_vtt_file(view, self.viz_id)
                rel_vtt_path = re.search(
                    "mmif-viz-cache/.*", vtt_path).group(0)
                html.write(
                    f'    <track kind="captions" srclang="en" src="/{rel_vtt_path}" label="transcript" default/>\n')
        html.write("</video>\n")
        return html.getvalue()


# -- Annotation Classes --

class InfoTab(AnnotationTab):
    def __init__(self, mmif):
        self.id = "info"
        self.tab_name = "Info"
        super().__init__(mmif)

    def render(self):
        mmif = self.mmif
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
            s.write('%s  %s  %s  %d\n' %
                    (view.id, app, status, len(view.annotations)))
            if len(view.annotations) > 0:
                s.write('\n')
                types = Counter([a.at_type.shortname
                                for a in view.annotations])
                for attype, count in types.items():
                    s.write('    %4d %s\n' % (count, attype))
            s.write('\n')
        s.write("</pre>")
        return s.getvalue()


class AnnotationTableTab(AnnotationTab):
    def __init__(self, mmif):
        self.id = "annotations"
        self.tab_name = "Annotations"
        super().__init__(mmif)

    def render(self):
        mmif = self.mmif
        s = StringIO('Howdy')
        for view in mmif.views:
            status = get_status(view)
            s.write('<p><b>%s  %s</b>  %s  %d annotations</p>\n'
                    % (view.id, view.metadata.app, status, len(view.annotations)))
            s.write("<blockquote>\n")
            s.write("<table cellspacing=0 cellpadding=5 border=1>\n")
            def limit_len(str): return str[:500] + \
                "  . . .  }" if len(str) > 500 else str
            for annotation in view.annotations:
                s.write('  <tr>\n')
                s.write('    <td>%s</td>\n' % annotation.id)
                s.write('    <td>%s</td>\n' % annotation.at_type.shortname)
                s.write('    <td>%s</td>\n' %
                        limit_len(get_properties(annotation)))
                s.write('  </tr>\n')
            s.write("</table>\n")
            s.write("</blockquote>\n")
        return s.getvalue()


class JSTreeTab(AnnotationTab):
    def __init__(self, mmif):
        self.id = "tree"
        self.tab_name = "Tree"
        super().__init__(mmif)

    def render(self):
        mmif = self.mmif
        return render_template('interactive.html', mmif=mmif, aligned_views=[])


class NERTab(AnnotationTab):
    def __init__(self, mmif, view):
        super().__init__(mmif, view)

    def render(self):
        metadata = self.view.metadata.contains.get(Uri.NE)
        ner_document = metadata.get('document')
        return displacy.visualize_ner(self.mmif, self.view, ner_document, current_app.root_path)


class VTTTab(AnnotationTab):
    def __init__(self, mmif, view, viz_id):
        self.viz_id = viz_id
        super().__init__(mmif, view)

    def render(self):
        vtt_filename = get_vtt_file(self.view, self.viz_id)
        with open(vtt_filename) as vtt_file:
            vtt_content = vtt_file.read()
        return f"<pre>{vtt_content}</pre>"


class OCRTab(AnnotationTab):
    def __init__(self, mmif, view, viz_id):
        self.viz_id = viz_id
        self.vid_path = mmif.get_documents_by_type(DocumentTypes.VideoDocument)[
            0].location_path()

        super().__init__(mmif, view)

    def render(self):
        return render_template("pre-ocr.html", view_id=self.view.id, tabname=self.tab_name, mmif_id=self.viz_id)
        # prepare_ocr(self.mmif, self.view, self.viz_id)
        # return render_ocr_page(self.viz_id, self.vid_path, self.view.id, 0)


def render_ocr_page(mmif_id, vid_path, view_id, page_number):
    """
    Renders a single OCR page by iterating through frames and displaying the 
    contents/alignments. Note: this needs to be a separate function (not a method
    in OCRTab) because it is called by the server when the page is changed.
    """
    # Path for storing temporary images generated by cv2
    cv2_vid = cv2.VideoCapture(vid_path)
    tn_data_fname = cache.get_cache_root() / mmif_id / f"{view_id}-pages.json"
    thumbnail_pages = json.load(open(tn_data_fname))
    page = thumbnail_pages[str(page_number)]
    prev_frame_cap = None
    path = make_image_directory(mmif_id, view_id)
    for frame_num, frame in page:
        # If index is range instead of frame...
        if frame.get("range"):
            frame_num = (int(frame["range"][0]) + int(frame["range"][1])) / 2
        cv2_vid.set(1, frame_num)
        _, frame_cap = cv2_vid.read()
        if frame_cap is None:
            raise FileNotFoundError(f"Video file {vid_path} not found!")

        # Double check histogram similarity of "repeat" frames -- if they're significantly different, un-mark as repeat
        if prev_frame_cap is not None and frame["repeat"] and not is_duplicate_image(prev_frame_cap, frame_cap,
                                                                                     cv2_vid):
            frame["repeat"] = False
        with tempfile.NamedTemporaryFile(dir=str(path), suffix=".jpg", delete=False) as tf:
            cv2.imwrite(tf.name, frame_cap)
            # "id" is just the name of the temp image file
            frame["id"] = pathlib.Path(tf.name).name
        prev_frame_cap = frame_cap

    tn_page_html = render_template(
        'ocr.html', vid_path=vid_path, view_id=view_id, page=page,
        n_pages=len(thumbnail_pages), page_number=str(page_number), mmif_id=mmif_id)
    return tn_page_html
