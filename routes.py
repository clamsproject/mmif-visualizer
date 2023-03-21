import os
import sys
import datetime
import secrets

import cv2


from io import StringIO
from string import Template

import displacy
import requests
import tempfile
import re
import ast
import html

from flask import Flask, request, render_template, flash, redirect, jsonify
from werkzeug.utils import secure_filename

from mmif.serialize import Mmif, View
from mmif.vocabulary import AnnotationTypes
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri

from utils import app, render_ocr, get_media, prep_annotations, change_page
# from ocr import render_ocr

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ocrpage', methods=['POST'])
def ocrpage():
    try:
        data = request.form.to_dict()
        frames_pages = eval(html.unescape(data['frames_pages']))
        alignments = eval(html.unescape(data['alignments']))
        text_docs = eval(html.unescape(data['text_docs']))
        page_number = int(data['page_number'])

        return (render_ocr(data['vid_path'], frames_pages, alignments, text_docs, page_number))
    except Exception as e:
        print(f"Unexpected error of type {type(e)}: {e}")
        pass

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
