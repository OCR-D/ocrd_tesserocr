export

SHELL = /bin/bash
PYTHON = python
PIP = pip
LOG_LEVEL = INFO
PYTHONIOENCODING=utf8

# Docker container tag
DOCKER_TAG = 'ocrd/tesserocr'

# BEGIN-EVAL makefile-parser --make-help Makefile

help:
	@echo ""
	@echo "  Targets"
	@echo ""
	@echo "    deps-ubuntu    Dependencies for deployment in an ubuntu/debian linux"
	@echo "    patch-header   Add default parameter to regain downward compatibility"
	@echo "    deps-pip       Install python deps via pip"
	@echo "    deps-pip-test  Install testing deps via pip"
	@echo "    install        Install"
	@echo "    docker         Build docker image"
	@echo "    test           Run test"
	@echo "    repo/assets    Clone OCR-D/assets to ./repo/assets"
	@echo "    test/assets    Setup test assets"
	@echo "    assets-clean   Remove symlinks in test/assets"
	@echo ""
	@echo "  Variables"
	@echo ""
	@echo "    DOCKER_TAG  Docker container tag"

# END-EVAL

# Add default parameter to regain downward compatibility
.PHONY: patch-header
patch-header:
	sed -i 's/, bool textonly[)];/, bool textonly = false);/g' /usr/include/tesseract/renderer.h

# Dependencies for deployment in an ubuntu/debian linux
deps-ubuntu:
	sudo apt-get install -y \
		libxml2-utils \
		libimage-exiftool-perl \
		libtesseract-dev \
		libleptonica-dev \
		tesseract-ocr-eng

# Install python deps via pip
deps-pip:
	$(PIP) install -r requirements.txt

# Install testing deps via pip
deps-pip-test:
	$(PIP) install -r requirements_test.txt

deps: deps-ubuntu deps-pip

# Install
install:
	$(PIP) install .

# Build docker image
docker:
	docker build -t $(DOCKER_TAG) .

.PHONY: test install deps deps-ubuntu deps-pip deps-pip-test help
# Run test
test: test/assets
	$(PYTHON) -m pytest test

#
# Assets
#

# Clone OCR-D/assets to ./repo/assets
repo/assets:
	mkdir -p $(dir $@)
	git clone https://github.com/OCR-D/assets "$@"


# Setup test assets
test/assets: repo/assets
	mkdir -p $@
	cp -r -t $@ repo/assets/data/*

.PHONY: assets-clean
# Remove symlinks in test/assets
assets-clean:
	rm -rf test/assets
