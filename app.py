import os
import secrets
import sys
from pathlib import Path
from threading import Thread

import shortuuid
from flask import request, render_template, flash, send_from_directory, session, redirect
from mmif.serialize import Mmif

import cache
from cache import set_last_access, cleanup
from utils import app, render_ocr, get_media, prep_annotations, prepare_ocr_visualization


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ocr', methods=['POST'])
def ocr():
    try:
        data = dict(request.json)
        mmif_str = open(cache.get_cache_path() / data["mmif_id"] / "file.mmif").read()
        mmif = Mmif(mmif_str)
        ocr_view = mmif.get_view_by_id(data["view_id"])
        return prepare_ocr_visualization(mmif, ocr_view, data["mmif_id"])
    except Exception as e:
        return f'<p class="error">{e}</h1>'


@app.route('/ocrpage', methods=['POST'])
def ocrpage():
    data = request.json
    try:
        return render_ocr(data["mmif_id"], data['vid_path'], data["view_id"], data["page_number"])
    except Exception as e:
        return f'<p class="error">Unexpected error of type {type(e)}: {e}</h1>'


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # NOTE. Uses of flash() originally gaven a RuntimeError (The session is
    # unavailable because no secret key was set). This was solved in the
    # __main__ block by setting a key.
    if request.method == 'POST':
        # Check if request is coming from elasticsearch
        if 'data' in request.form:
            return upload_file(request.form['data'])
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
            return upload_file(file)

    return render_template('upload.html')


@app.route('/display/<viz_id>')
def display(viz_id):
    try:
        path = cache.get_cache_path() / viz_id
        set_last_access(path)
        with open(os.path.join(path, "index.html")) as f:
            html_file = f.read()
        return html_file
    except FileNotFoundError:
        flash("File not found -- please upload again (it may have been deleted to clear up cache space).")
        return redirect("/upload")


@app.route('/uv/<path:path>')
def send_js(path):
    return send_from_directory("uv", path)


def render_mmif(mmif_str):
    mmif = Mmif(mmif_str)
    media = get_media(mmif)
    annotations = prep_annotations(mmif)
    return render_template('player.html',
                           media=media, annotations=annotations)


def upload_file(file):
    # Save file locally
    uuid = shortuuid.uuid()
    session["mmif_id"] = uuid
    app.logger.debug(uuid)
    path = Path(app.root_path) / 'static' / 'tmp' / uuid
    os.makedirs(path)
    set_last_access(path)
    file.save(os.path.join(path, "file.mmif"))
    with open(os.path.join(path, "file.mmif")) as fh:
        mmif_str = fh.read()
    html_page = render_mmif(mmif_str)
    with open(os.path.join(path, "index.html"), "w") as f:
        f.write(html_page)

    # Perform cleanup
    t = Thread(target=cleanup)
    t.daemon = True
    t.run()

    agent = request.headers.get('User-Agent')
    if 'curl' in agent.lower():
        return f"Visualization ID is {uuid}\nYou can access the visualized file at /display/{uuid}\n"
    return redirect(f"/display/{uuid}", code=301)


if __name__ == '__main__':
    # Make path for temp files
    cache_path = cache.get_cache_path()
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    # to avoid runtime errors for missing keys when using flash()
    alphabet = 'abcdefghijklmnopqrstuvwxyz1234567890'
    app.secret_key = ''.join(secrets.choice(alphabet) for i in range(36))

    port = 5000
    if len(sys.argv) > 2 and sys.argv[1] == '-p':
        port = int(sys.argv[2])
        
    app.run(port=port, host='0.0.0.0', debug=True, use_reloader=False)
