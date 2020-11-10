import json
import os
import displacy
import requests
import tempfile

from flask import Flask, request, render_template, flash, redirect
from werkzeug.utils import secure_filename

from mmif.serialize import *
from mmif.vocabulary import AnnotationTypes
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri


app = Flask(__name__)


# This is where the applicaiton looks for files, it should be a symbolic link to
# /mmif-viz/static
PATH_PREFIX = 'static'


def view_to_vtt(alignment_view):
    vtt_file = get_alignments(alignment_view)
    return os.sep.join(vtt_file.name.split(os.sep)[-2:])


def get_alignments(alignment_view):
    # TODO: maybe just use a string buffer
    vtt_file = tempfile.NamedTemporaryFile('w', dir="static/", suffix='.vtt', delete=False)
    for annotation in alignment_view.annotations:
        if annotation.at_type == "vanilla-forced-alignment":
            # VTT specifically requires timestamps expressed in miliseconds
            # ISO format can have up to 6 below the decimal point, on the other hand
            # Assuming start and end are in miliseconds
            start = annotation.properties['start']
            end = annotation.properties['end']
            text = annotation.properties['word']
            vtt_file.write(f'{start} --> {end}\n{text}\n\n')
    return vtt_file


def html_video(vpath, vtt_srcview):
    sources = f'<source src=\"{vpath}\"> '
    if vtt_srcview is not None:
        vtt_path = view_to_vtt(vtt_srcview)
        sources += f'<track kind="subtitles" srclang="en" src="{vtt_path}" default> '
    return f"<video controls> {sources} </video>"


def html_text(tpath):
    with open(tpath) as t_file:
        return f"<pre width=\"100%\">\n{t_file.read()}\n</pre>"


def html_img(ipath, overlay_annotation=None):
    return f""" <canvas id="imgCanvas" width="350" height="1000"></canvas>
                    <script>
                        var ann_view = {overlay_annotation if overlay_annotation is not None else {{"annotations: []"}}}
                        var canvas = document.getElementById('imgCanvas');
                        var context = canvas.getContext('2d');
                        var imageObj = new Image();
                        imageObj.src = '{ipath}';
                        imageObj.onload = function() {{
                            var imgWidth = imageObj.naturalWidth;
                            var screenWidth  = canvas.width;
                            var scaleX = 1;
                            if (imgWidth > screenWidth)
                                scaleX = screenWidth/imgWidth;
                            var imgHeight = imageObj.naturalHeight;
                            var screenHeight = canvas.height;
                            var scaleY = 1;
                            if (imgHeight > screenHeight)
                                scaleY = screenHeight/imgHeight;
                            var scale = scaleY;
                            if(scaleX < scaleY)
                                scale = scaleX;
                            if(scale < 1){{
                                imgHeight = imgHeight*scale;
                                imgWidth = imgWidth*scale;
                            }}
                            canvas.height = imgHeight;
                            canvas.width = imgWidth;
                            context.drawImage(imageObj, 0, 0, imageObj.naturalWidth, imageObj.naturalHeight, 0,0, imgWidth, imgHeight);
                                                    context.beginPath();
                            context.lineWidth = "4";
                            context.strokeStyle = "green";
                            context.scale(scale, scale);
                            for (var i=0; i < ann_view["annotations"].length; i++){{
                                var box = ann_view["annotations"][i];
                                var coord = (box["feature"]["box"]);
                                x = coord[0];
                                y = coord[1];
                                w = coord[2] - coord[0];
                                h = coord[3] - coord[1];
                                context.rect(x, y, w, h);
                            }}
                            context.stroke();
                        }}
                    </script>"""


def html_audio(apath):
    return f"<audio controls src={apath}></audio>"


def display_mmif(mmif_str):

    mmif = Mmif(mmif_str)

    # TODO: the order in this list decides the default view in the display
    # (which is the first one), this used to be done specifically by adding the
    # video first, but it is now determined by the order in the documents list
    # in the MMIF object. May need to change that if the video is not the first
    # one in the MMIF file.
    found_media = []

    for document in mmif.documents:
        doc_type = get_document_type_short_form(document)
        doc_path = PATH_PREFIX + document.location
        if doc_type == 'Text':
            found_media.append(('Text', html_text(doc_path)))
        elif doc_type == 'Video':
            fa_view = get_alignment_view(mmif)
            found_media.append(("Video", html_video(doc_path, fa_view)))
        elif doc_type == 'Audio':
            found_media.append(("Audio", html_audio(doc_path)))
        elif doc_type == 'Image':
            # TODO: this is broken now
            try:
                tboxes = mmif.get_view_contains(AnnotationTypes.TBOX)
            except:
                tboxes = None
            found_media.append(("Image", html_img(doc_path, tboxes)))

    annotations = prep_ann_for_viz(mmif)
    return render_template('player_page.html',
                           mmif=mmif,
                           media=found_media,
                           annotations=annotations)


def get_document_type_short_form(document):
    document_type = os.path.split(document.at_type)[1]
    return document_type[:-8]


def prep_ann_for_viz(mmif):
    anns = [("MMIF", "<pre>" + mmif.serialize(pretty=True) + "</pre>")]
    ner_view = get_first_ner_view(mmif)
    alignment_view = get_alignment_view(mmif)
    if alignment_view is not None:
        vtt_file = view_to_vtt(alignment_view)
        anns.append(("WEBVTT", '<pre>' + open(vtt_file).read() + '</pre>'))
    if ner_view is not None:
        anns.append(("Entities", displacy.get_displacy(mmif)))
    return anns


def get_first_ner_view(mmif):
    for view in mmif.views:
        if Uri.NE in view.metadata.contains:
            return view


def get_alignment_view(mmif):
    # TODO:
    # - replace this with new way to find the alignments
    # - (krim @ 11/8/19): not just `FA` but for more robust recognition
    #   of text-time alignment types
    for view in mmif.views:
        if "vanilla-forced-alignment" in view.metadata.contains:
            return view


@app.route('/display')
def display_file():
    mmif_str = requests.get(request.args["file"]).text
    return display_mmif(mmif_str)


def upload_display(filename):
    f = open("temp/" + filename)
    mmif_str = f.read()
    f.close()
    return display_mmif(mmif_str)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join('temp', filename))
            return upload_display(filename)
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form> 
    '''


@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    # TODO (krim @ 10/1/19): parameterize port number
    app.run(port=5000, host='0.0.0.0', debug=True)
