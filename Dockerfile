FROM ocrd/core:v2.62.0 AS base
# set proper locales
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
# install ocrd-tesserocr (until here commands for installing tesseract-ocr)
ARG VCS_REF
ARG BUILD_DATE
LABEL \
    maintainer="https://ocr-d.de/kontakt" \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url="https://github.com/OCR-D/ocrd_tesserocr" \
    org.label-schema.build-date=$BUILD_DATE

ENV PYTHONIOENCODING utf8

# set TESSDATA_PREFIX
ENV TESSDATA_PREFIX /usr/local/share/tessdata

# set frontend non-interactive to silence interactive tzdata config
ARG DEBIAN_FRONTEND=noninteractive


# install common tools and tesseract build dependencies
# use provided leptonica
# tzdata required for proper timezone settings
RUN apt-get update && apt-get install -y \
	apt-utils \
	build-essential \
	g++ \
	git \
	libjpeg-dev \
	libgif-dev \
	libwebp-dev \
	libopenjp2-7-dev \
	libpng-dev \
	libtiff-dev \
	libtool \
	pkg-config \
	tzdata \
	xzgv \
	zlib1g-dev \
	libleptonica-dev \
	libpango1.0-dev \
	libicu-dev \
	autotools-dev \
	automake \
	libcurl4-nss-dev \
	libarchive-dev

# set proper date and timezone in container
RUN echo "Europe/Berlin" > /etc/timezone
RUN ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime
RUN dpkg-reconfigure -f noninteractive tzdata

# diagnostic output - check timezone settings
# RUN cat /etc/timezone

# avoid HOME/.local/share (hard to predict USER here)
# so let XDG_DATA_HOME coincide with fixed system location
# (can still be overridden by derived stages)
ENV XDG_DATA_HOME /usr/local/share

WORKDIR /build-ocrd_tesserocr
COPY setup.py .
COPY ocrd_tesserocr/ocrd-tool.json .
COPY README.md .
COPY requirements.txt .
COPY requirements_test.txt .
COPY ocrd_tesserocr ./ocrd_tesserocr
COPY repo/tesserocr ./repo/tesserocr
COPY repo/tesseract ./repo/tesseract
COPY Makefile .
RUN apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && make deps install-tesseract install-tesserocr install \
    && rm -rf /build-ocrd_tesserocr \
    && apt-get -y remove --auto-remove g++ libtesseract-dev make

# PPA tessdata prefix (= ocrd_tesserocr moduledir) is owned by root
# next line causes failure because tesseract-ocr-eng not existing. Not sure if needed, so skipping
# RUN sudo chmod go+w `dpkg-query -L tesseract-ocr-eng | sed -n s,/eng.traineddata,,p`
RUN ocrd resmgr download ocrd-tesserocr-recognize Fraktur.traineddata
RUN ocrd resmgr download ocrd-tesserocr-recognize deu.traineddata
RUN ocrd resmgr download ocrd-tesserocr-recognize eng.traineddata

WORKDIR /data
VOLUME /data
