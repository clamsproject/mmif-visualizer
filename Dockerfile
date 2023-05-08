FROM python:3.6-slim-buster

# Additional required files for openCV
RUN apt-get update
RUN apt-get install ffmpeg libsm6 libxext6  -y

WORKDIR ./app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY ./ ./

CMD ["python", "app.py"]
