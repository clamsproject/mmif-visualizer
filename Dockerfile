FROM python:3.6-buster

COPY ./ ./app
WORKDIR ./app

RUN pip3 install -r requirements.txt

CMD ["python", "app.py"]
