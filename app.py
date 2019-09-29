import os

from clams import Mmif
from clams.vocab import MediaTypes
from flask import Flask, request, render_template, flash, redirect
from werkzeug.utils import secure_filename

app = Flask(__name__)


def display_mmif(mmif_str):
    mmif = Mmif(mmif_str)
    # TODO (krim @ 9/28/19): catch error when no video file specified in the mmif
    # TODO (krim @ 9/28/19): implement this to flexible to any media type (in order of v->a->t)
    media_fname = 'static' + mmif.get_medium_location(md_type=MediaTypes.V)
    annotations = prep_ann_for_viz(mmif)
    return render_template('player_page.html', mmif=mmif, media=media_fname, annotations=annotations)


def prep_ann_for_viz(mmif):
    anns = [("raw", str(mmif)), ("PP", mmif.pretty())]

    return anns


@app.route('/display')
def display_file():
    mmif_str = request.get_data()
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
    app.run(port=5000, host='0.0.0.0', debug=True)
