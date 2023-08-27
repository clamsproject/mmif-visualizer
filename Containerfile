FROM ghcr.io/clamsproject/clams-python-opencv4:1.0.0

WORKDIR ./app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY ./ ./

CMD ["python", "app.py"]