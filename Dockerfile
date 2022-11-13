FROM ubuntu:latest
FROM python:3.10.6-slim-buster

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get install -y curl
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
# RUN apt-get install -y python3.9-distutils
RUN python3 get-pip.py --user

RUN apt-get install -y ffmpeg
RUN apt-get install -y build-essential
RUN pip install -U discord.py \
    pynacl \
    cython \
    cchardet

COPY requirements.txt requirements.txt 
RUN pip install -U -r requirements.txt 

COPY . .

CMD ["python3", "main.py"]