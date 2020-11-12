FROM ubuntu:20.04


RUN apt-get update && \
    apt-get install -y git python3 python3-pip python3-setuptools

COPY ./ ./app
WORKDIR ./app
RUN pip3 install -r requirements.txt


ENTRYPOINT ["python3"]
CMD ["app.py"]
