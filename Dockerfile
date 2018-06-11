FROM ocrd/core
MAINTAINER OCR-D
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONIOENCODING utf8
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

WORKDIR /build-ocrd
COPY setup.py .
COPY requirements.txt .
COPY README.rst .
COPY LICENSE .
RUN apt-get update && \
    apt-get -y install --no-install-recommends \
    ca-certificates \
    sudo \
    make \
    git
COPY Makefile .
RUN make deps-ubuntu
RUN git clone https://github.com/sirfz/tesserocr && \
    cd tesserocr && \
    python3 setup.py install && \
    cd .. && \
    mkdir data
COPY ocrd_tesserocr ./ocrd_tesserocr
RUN pip3 install --upgrade pip
RUN make deps-pip install

ENTRYPOINT ["/bin/sh", "-c"]
