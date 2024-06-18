import hashlib
import os
import secrets
import sys
from threading import Thread
from shutil import rmtree

from flask import Flask, request, render_template, flash, send_from_directory, redirect
from mmif.serialize import Mmif
from mmif.vocabulary import DocumentTypes

import cache
from cache import set_last_access, cleanup
import traceback
from render import render_documents, render_annotations, prepare_ocr, render_ocr_page

# these two static folder-related params are important, do not remove
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'your_secret_key_here'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ocr', methods=['POST'])
def ocr():
    if "page_number" not in request.json:
        build_ocr_tab(request.json)
        request.json["page_number"] = 0
    #     return serve_first_ocr_page(request.json)
    # else:
    return serve_ocr_page(request.json)


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


@app.route('/decache', methods=['GET', 'POST'])
def invalidate_cache():
    app.logger.debug(f"Request to invalidate cache on {request.args}")
    if not request.args.get('viz_id'):
        app.logger.debug("Invalidating entire cache.")
        cache.invalidate_cache()
        return redirect("/upload")
    viz_id = request.args.get('viz_id')
    in_mmif = open(cache.get_cache_root() / viz_id / 'file.mmif', 'rb').read()
    app.logger.debug(f"Invalidating {viz_id} from cache.")
    cache.invalidate_cache([viz_id])
    return upload_file(in_mmif)


@app.route('/display/<viz_id>')
def display(viz_id):
    path = cache.get_cache_root() / viz_id
    app.logger.debug(f"Displaying visualization {viz_id} from {path}")
    if os.path.exists(path / "index.html"):
        app.logger.debug(f"Visualization {viz_id} found in cache.")
        set_last_access(path)
        with open(os.path.join(path, "index.html")) as f:
            html_file = f.read()
        return html_file
    else:
        app.logger.debug(f"Visualization {viz_id} not found in cache.")
        rmtree(path)
        flash("File not found -- please upload again (it may have been deleted to clear up cache space).")
        return redirect("/upload")


@app.route('/uv/<path:path>')
def send_js(path):
    return send_from_directory("uv", path)


def render_mmif(mmif_str, viz_id):
    mmif = Mmif(mmif_str)
    rendered_documents = render_documents(mmif, viz_id)
    rendered_annotations = render_annotations(mmif, viz_id)
    return render_template('player.html',
                           docs=rendered_documents,
                           viz_id=viz_id,
                           annotations=rendered_annotations)


def build_ocr_tab(data):
    """
    Prepares OCR (at load time, due to lazy loading)
    """
    try:
        data = dict(request.json)
        mmif_str = open(cache.get_cache_root() /
                        data["mmif_id"] / "file.mmif").read()
        mmif = Mmif(mmif_str)
        ocr_view = mmif.get_view_by_id(data["view_id"])
        prepare_ocr(mmif, ocr_view, data["mmif_id"])
        request.json["vid_path"] = mmif.get_documents_by_type(DocumentTypes.VideoDocument)[
                0].location_path()

    except Exception as e:
        app.logger.error(f"{e}\n{traceback.format_exc()}")
        return f'<p class="error">Error: {e} Check the server log for more information.</h1>'


def serve_ocr_page(data):
    """
    Serves subsequent OCR pages
    """
    try:
        return render_ocr_page(data["mmif_id"], data['vid_path'], data["view_id"], data["page_number"])
    except Exception as e:
        return f'<p class="error">Unexpected error of type {type(e)}: {e}</h1>'


def upload_file(in_mmif):
    # Save file locally
    in_mmif_bytes = in_mmif if isinstance(in_mmif, bytes) else in_mmif.read()
    in_mmif_str = in_mmif_bytes.decode('utf-8')
    viz_id = hashlib.sha1(in_mmif_bytes).hexdigest()
    app.logger.debug(f"Visualization ID: {viz_id}")
    path = cache.get_cache_root() / viz_id
    app.logger.debug(f"Visualization Directory: {path}")
    try:
        os.makedirs(path)
        set_last_access(path)
        with open(path / 'file.mmif', 'w') as in_mmif_file:
            app.logger.debug(f"Writing original MMIF to {path / 'file.mmif'}")
            in_mmif_file.write(in_mmif_str)
        html_page = render_mmif(in_mmif_str, viz_id)
        with open(os.path.join(path, "index.html"), "w") as f:
            f.write(html_page)
    except FileExistsError:
        app.logger.debug("Visualization already cached")
    finally:
        # Perform cleanup
        t = Thread(target=cleanup)
        t.daemon = True
        t.run()

    agent = request.headers.get('User-Agent')
    if 'curl' in agent.lower():
        return f"Visualization ID is {viz_id}\nYou can access the visualized file at {request.url_root}display/{viz_id}\n"
    return redirect(f"/display/{viz_id}", code=301)


if __name__ == '__main__':
    # Make path for temp files
    cache_path = cache.get_cache_root()
    cache_symlink_path = os.path.join(
        app.static_folder, cache._CACHE_DIR_SUFFIX)
    if os.path.islink(cache_symlink_path):
        os.unlink(cache_symlink_path)
    elif os.path.exists(cache_symlink_path):
        raise RuntimeError(f"Expected {cache_symlink_path} to be a symlink (for re-linking to a new cache dir, "
                           f"but it is a real path.")
    os.symlink(cache_path, cache_symlink_path)

    # to avoid runtime errors for missing keys when using flash()
    alphabet = 'abcdefghijklmnopqrstuvwxyz1234567890'
    app.secret_key = ''.join(secrets.choice(alphabet) for i in range(36))

    port = 5000
    if len(sys.argv) > 2 and sys.argv[1] == '-p':
        port = int(sys.argv[2])

    app.run(port=port, host='0.0.0.0', debug=True, use_reloader=True)
