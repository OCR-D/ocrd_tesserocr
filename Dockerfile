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
RUN make deps-ubuntu && \
    apt-get install -y --no-install-recommends \
    g++ \
    tesseract-ocr-script-frak \
    tesseract-ocr-deu \
    && make deps install \
    && rm -rf /build-ocrd \
    && apt-get -y remove --auto-remove g++ libtesseract-dev make
