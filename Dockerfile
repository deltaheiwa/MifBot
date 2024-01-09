FROM ubuntu:latest
FROM python:3.11.6-slim

ENV POETRY_VERSION=1.2.2

RUN apt-get update
RUN apt-get install -y software-properties-common
# RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get install -y curl
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
# RUN apt-get install -y python3.9-distutils
RUN python3 get-pip.py --user
RUN apt-get install -y ffmpeg
RUN apt-get install -y build-essential

RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /code
COPY poetry.lock pyproject.toml /code/
RUN POETRY_VIRTUALENVS_CREATE=false poetry install --no-interaction --no-ansi

COPY . /code
RUN chmod +x run_bot.bash
CMD ["python3", "main.py"]