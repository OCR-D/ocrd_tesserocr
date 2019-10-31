FROM ocrd/core:edge
MAINTAINER OCR-D
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONIOENCODING utf8

WORKDIR /build-ocrd
COPY setup.py .
COPY requirements.txt .
COPY requirements_test.txt .
COPY ocrd_tesserocr ./ocrd_tesserocr
COPY Makefile .
RUN apt-get update && \
    apt-get -y install --no-install-recommends \
    libtesseract-dev \
    tesseract-ocr \
    wget
RUN pip3 install --upgrade pip
RUN make PYTHON=python3 PIP=pip3 deps install

ENTRYPOINT ["/bin/sh", "-c"]
