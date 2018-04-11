export

SHELL = /bin/bash
PYTHON = python
PYTHONPATH := .:$(PYTHONPATH)
PIP = pip
LOG_LEVEL = INFO
PYTHONIOENCODING=utf8

# Docker container tag
DOCKER_TAG = 'ocrd/ocrd_tesserocr'

# BEGIN-EVAL makefile-parser --make-help Makefile

help:
	@echo ""
	@echo "  Targets"
	@echo ""
	@echo "    deps-ubuntu  Dependencies for deployment in an ubuntu/debian linux"
	@echo "    deps-pip     Install python deps via pip"
	@echo "    install      Install"
	@echo "    docker       Build docker image"
	@echo "    test         Run test"
	@echo ""
	@echo "  Variables"
	@echo ""
	@echo "    DOCKER_TAG  Docker container tag"

# END-EVAL

# Dependencies for deployment in an ubuntu/debian linux
deps-ubuntu:
	apt install -y \
		libxml2-utils \
		libtesseract-dev \
		libleptonica-dev \
		tesseract-ocr-eng

# Install python deps via pip
deps-pip:
	$(PIP) install -r requirements.txt

# Install testing deps via pip
deps-pip-test:
	$(PIP) install -r requirements_test.txt

# Install
install:
	$(PIP) install .

# Build docker image
docker:
	docker build -t $(DOCKER_TAG) .

.PHONY: test
# Run test
test:
	python -m pytest test

#
# Assets
#

# Clone the ocrd-assets repo for sample files
assets: ocrd-assets test/assets

ocrd-assets:
	git clone https://github.com/OCR-D/ocrd-assets

test/assets:
	mkdir -p test/assets
	cp -r -t test/assets ocrd-assets/data/*

# Start asset server at http://localhost:5001
assets-server:
	cd ocrd-assets && make start

# Remove symlinks in test/assets
assets-clean:
	rm -rf test/assets
