FROM python:3.6-buster

WORKDIR ./app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

# Additional required files for openCV
RUN apt-get update
RUN apt-get install ffmpeg libsm6 libxext6  -y

COPY ./ ./

CMD ["python", "app.py"]
