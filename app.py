import os
import sys
import secrets
import html
import datetime
import ast
import json

from flask import request, render_template, flash, redirect, send_from_directory, session
from werkzeug.utils import secure_filename
from mmif.serialize import Mmif

from utils import app, render_ocr, get_media, prep_annotations

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ocrpage', methods=['POST'])
def ocrpage():
    data = request.json
    try:
        page_number = data["page_number"]
        view_id = data["view_id"]
        return (render_ocr(data['vid_path'], data["view_id"], page_number))
    except Exception as e:
        return f'<p class="error">Unexpected error of type {type(e)}: {e}</h1>'
        pass

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # NOTE. Uses of flash() originally gaven a RuntimeError (The session is
    # unavailable because no secret key was set). This was solved in the
    # __main__ block by setting a key.
    if request.method == 'POST':
        # Check if request is coming from elasticsearch
        if 'data' in request.form:
            return render_mmif(request.form['data'])
        # Otherwise, check if the post request has the file part
        elif 'file' not in request.files:
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


@app.route('/uv/<path:path>')
def send_js(path):
    return send_from_directory("uv", path)


def render_mmif(mmif_str):
    mmif = Mmif(mmif_str)
    media = get_media(mmif)
    annotations = prep_annotations(mmif)
    return render_template('player.html',
                           mmif=mmif, media=media, annotations=annotations)


if __name__ == '__main__':
    # Make path for temp files
    tmp_path = '/app/static/tmp'
    if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)


    # to avoid runtime errors for missing keys when using flash()
    alphabet = 'abcdefghijklmnopqrstuvwxyz1234567890'
    app.secret_key = ''.join(secrets.choice(alphabet) for i in range(36))

    port = 5000
    if len(sys.argv) > 2 and sys.argv[1] == '-p':
        port = int(sys.argv[2])
    app.run(port=port, host='0.0.0.0', debug=True)
