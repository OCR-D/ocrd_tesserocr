FROM ocrd/core
ARG VCS_REF
ARG BUILD_DATE
LABEL \
    maintainer="https://ocr-d.de/kontakt" \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url="https://github.com/OCR-D/ocrd_tesserocr" \
    org.label-schema.build-date=$BUILD_DATE

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONIOENCODING utf8

# avoid HOME/.local/share (hard to predict USER here)
# so let XDG_DATA_HOME coincide with fixed system location
# (can still be overridden by derived stages)
ENV XDG_DATA_HOME /usr/local/share
# allow using resmgr data location but still keep internal module location
RUN mkdir -p $XDG_DATA_HOME/ocrd-resources
RUN ln -rs /usr/share/tesseract-ocr/4.00/tessdata $XDG_DATA_HOME/ocrd-resources/ocrd-tesserocr-recognize

WORKDIR /build-ocrd
COPY setup.py .
COPY ocrd_tesserocr/ocrd-tool.json .
COPY README.md .
COPY requirements.txt .
COPY requirements_test.txt .
COPY ocrd_tesserocr ./ocrd_tesserocr
COPY Makefile .
RUN make deps-ubuntu && \
    apt-get install -y --no-install-recommends \
    g++ \
    && make deps install \
    && rm -rf /build-ocrd \
    && apt-get -y remove --auto-remove g++ libtesseract-dev make
RUN ocrd resmgr download ocrd-tesserocr-recognize Fraktur.traineddata
RUN ocrd resmgr download ocrd-tesserocr-recognize deu.traineddata

WORKDIR /data
VOLUME /data
