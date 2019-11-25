FROM ocrd/core
MAINTAINER OCR-D
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONIOENCODING utf8

WORKDIR /build-ocrd
COPY setup.py .
COPY README.md .
COPY requirements.txt .
COPY requirements_test.txt .
COPY ocrd_tesserocr ./ocrd_tesserocr
COPY Makefile .
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:alex-p/tesseract-ocr && \
    apt-get -y install --no-install-recommends \
    libtesseract-dev \
    tesseract-ocr \
    tesseract-ocr-script-frak \
    tesseract-ocr-deu \
    build-essential \
    && make deps install \
    && rm -rf /build-ocrd \
    && apt-get -y remove --auto-remove build-essential
