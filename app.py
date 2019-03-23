from flask import Flask, request
import requests

app = Flask(__name__)

@app.route('/display')
def display_file():
    print(request.args.get('file'))
    return requests.get(request.args.get('file')).text

@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run(port=4000, debug=True)
