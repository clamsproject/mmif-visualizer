import os

from flask import Flask, request, render_template, flash, redirect, url_for
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)

@app.route('/display')
def display_file():
    file = request.get_data()
    return render_template('player_page.html', mmif=file)

def upload_display(filename):
    with open("temp/" + filename) as f:
        file = f.read()
    return render_template('player_page.html', mmif=file)

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
