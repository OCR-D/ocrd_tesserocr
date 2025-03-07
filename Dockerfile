ARG DOCKER_BASE_IMAGE
FROM $DOCKER_BASE_IMAGE
# install ocrd-tesserocr (until here commands for installing tesseract-ocr)
ARG VCS_REF
ARG BUILD_DATE
LABEL \
    maintainer="https://ocr-d.de/kontakt" \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url="https://github.com/OCR-D/ocrd_tesserocr" \
    org.label-schema.build-date=$BUILD_DATE \
    org.opencontainers.image.vendor="DFG-Funded Initiative for Optical Character Recognition Development" \
    org.opencontainers.image.title="ocrd_tesserocr" \
    org.opencontainers.image.description="Tesseract OCR bindings" \
    org.opencontainers.image.source="https://github.com/OCR-D/ocrd_tesserocr" \
    org.opencontainers.image.documentation="https://github.com/OCR-D/ocrd_tesserocr/blob/${VCS_REF}/README.md" \
    org.opencontainers.image.revision=$VCS_REF \
    org.opencontainers.image.created=$BUILD_DATE \
    org.opencontainers.image.base.name=ocrd/core


# set frontend non-interactive to silence interactive tzdata config
ENV DEBIAN_FRONTEND noninteractive
# set proper locales
ENV PYTHONIOENCODING utf8
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

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
# avoid the need for an extra volume for persistent resource user db
# (i.e. XDG_CONFIG_HOME/ocrd/resources.yml)
ENV XDG_CONFIG_HOME /usr/local/share/ocrd-resources
ENV TESSDATA_PREFIX $XDG_DATA_HOME/tessdata

WORKDIR /build/ocrd_tesserocr
COPY . .
# prepackage ocrd-tool.json as ocrd-all-tool.json
RUN ocrd ocrd-tool ocrd_tesserocr/ocrd-tool.json dump-tools > $(dirname $(ocrd bashlib filename))/ocrd-all-tool.json
# install everything and reduce image size
RUN make deps-ubuntu \
    && make -j4 install GIT_SUBMODULE=: \
    && make -j4 install-tesseract-training GIT_SUBMODULE=: \
    && rm -rf /build/ocrd_tesserocr \
    && apt-get -y remove --auto-remove g++ libtesseract-dev make

RUN ocrd resmgr download ocrd-tesserocr-recognize Fraktur.traineddata && \
    ocrd resmgr download ocrd-tesserocr-recognize deu.traineddata && \
    # clean possibly created log-files/dirs of ocrd_network logger to prevent permission problems
    rm -rf /tmp/ocrd_*

# as discussed in ocrd_all#378, we do not want to manage more than one resource location
# to mount for model persistence; 
# with named volumes, the preinstalled models will be copied to the host and complemented
# by downloaded models; 
# tessdata is the only problematic module location
RUN mkdir -p $XDG_CONFIG_HOME
RUN mv $TESSDATA_PREFIX $XDG_CONFIG_HOME/ocrd-tesserocr-recognize
RUN ln -s $XDG_CONFIG_HOME/ocrd-tesserocr-recognize $TESSDATA_PREFIX
# finally, alias/symlink all ocrd-resources to /models for shorter mount commands
RUN mv $XDG_CONFIG_HOME /models && ln -s /models $XDG_CONFIG_HOME

WORKDIR /data
VOLUME /data
