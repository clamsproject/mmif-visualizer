import json
import os
import displacy
import bratify
import requests
import tempfile

from clams import Mmif
from clams.vocab import MediaTypes, AnnotationTypes
from lapps.discriminators import Uri
from flask import Flask, request, render_template, flash, redirect
from werkzeug.utils import secure_filename

app = Flask(__name__)


def view_to_vtt(alignment_view):
    vtt_file = tempfile.NamedTemporaryFile('w', dir="static/", suffix='.vtt', delete=False)
    vtt_file.write("WEBVTT\n\n")
    for annotation in alignment_view.annotations:
        if annotation.attype == AnnotationTypes.FA:
            print("FA!!!")
            # VTT specifically requires timestamps expressed in miliseconds
            # ISO format can have up to 6 below the decimal point, on the other hand
            vtt_file.write(f'{annotation.start[:-3]} --> {annotation.end[:-3]}\n{annotation.feature["text"]}\n\n')
    print(vtt_file.name)
    return os.sep.join(vtt_file.name.split(os.sep)[-2:])


def html_video(vpath, vtt_srcview):
    sources = f'<source src=\"{vpath}\"> '
    print(sources)
    if vtt_srcview is not None:
        vtt_path = view_to_vtt(vtt_srcview)
        sources += f'<track kind="subtitles" srclang="en" src="{vtt_path}" default> '
    return f"<video controls> {sources} </video>"


def html_text(tpath):
    with open(tpath) as t_file:
        return f"<pre width=\"100%\">\n{t_file.read()}\n</pre>"


def html_img(ipath):
    return f"<img src={ipath}>"


def html_audio(apath):
    return f"<audio controls src={apath}></audio>"


def display_mmif(mmif_str):
    mmif = Mmif(mmif_str)
    # TODO (krim @ 11/8/19): not just `FA` but for more robust recognition of text-time alignment types
    fa_view = None
    if AnnotationTypes.FA in mmif.contains:
        fa_view = mmif.get_view_by_id(mmif.contains[AnnotationTypes.FA])
    found_media = []    # the order in this list will decide the "default" view in the display
    # try:
    found_media.append(("Video", html_video('static' + mmif.get_medium_location(md_type=MediaTypes.V), fa_view)))
    # except:
    #     pass

    try:
        found_media.append(("Image", html_img('static' + mmif.get_medium_location(md_type=MediaTypes.I))))
    except:
        pass

    try:
        found_media.append(("Audio", html_audio('static' + mmif.get_medium_location(md_type=MediaTypes.A))))
    except:
        pass

    try:
        found_media.append(("Text", html_text('static' + mmif.get_medium_location(md_type=MediaTypes.T))))
    except:
        pass

    annotations = prep_ann_for_viz(mmif)
    return render_template('player_page.html', mmif=mmif, media=found_media, annotations=annotations)


def prep_ann_for_viz(mmif):
    anns = [("PP", "<pre>" + mmif.pretty() + "</pre>")]
    if Uri.NE in mmif.contains:
        anns.append(("Entities", displacy.get_displacy(mmif)))

    return anns


def get_brat(mmif, attype):
    brat_annotations = bratify.mmif_to_brat(mmif, attype)
    print(brat_annotations)
    if len(brat_annotations) > 0:
        brat_config = json.dumps(bratify.config[attype])
        return render_template("brat.html", brat_annotations=brat_annotations, brat_config=brat_config)
    return str(None)


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
