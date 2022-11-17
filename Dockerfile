FROM python:3.6-slim-buster

WORKDIR ./app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY ./ ./

CMD ["python", "app.py"]
