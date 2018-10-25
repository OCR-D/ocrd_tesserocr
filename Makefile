export

SHELL = /bin/bash
PYTHON = python
PIP = pip
LOG_LEVEL = INFO
PYTHONIOENCODING=utf8

# pytest args. Set to '-s' to see log output during test execution, '--verbose' to see individual tests. Default: '$(PYTEST_ARGS)'
PYTEST_ARGS =

# Docker container tag
DOCKER_TAG = 'ocrd/tesserocr'

# BEGIN-EVAL makefile-parser --make-help Makefile

help:
	@echo ""
	@echo "  Targets"
	@echo ""
	@echo "    patch-header  Add default parameter to regain downward compatibility"
	@echo "    deps          Install python deps via pip"
	@echo "    deps-test     Install testing python deps via pip"
	@echo "    install       Install"
	@echo "    docker        Build docker image"
	@echo "    test          Run test"
	@echo "    repo/assets   Clone OCR-D/assets to ./repo/assets"
	@echo "    test/assets   Setup test assets"
	@echo "    assets-clean  Remove symlinks in test/assets"
	@echo ""
	@echo "  Variables"
	@echo ""
	@echo "    PYTEST_ARGS  pytest args. Set to '-s' to see log output during test execution, '--verbose' to see individual tests. Default: '$(PYTEST_ARGS)'"
	@echo "    DOCKER_TAG   Docker container tag"

# END-EVAL

# Add default parameter to regain downward compatibility
.PHONY: patch-header
patch-header:
	# TODO remove if possible
	sed -i 's/, bool textonly[)];/, bool textonly = false);/g' /usr/include/tesseract/renderer.h

# # Dependencies for deployment in an ubuntu/debian linux
# deps-ubuntu:
#   apt-get install -y tesseract-ocr-eng

# Install python deps via pip
deps:
	$(PIP) install -r requirements.txt

# Install testing python deps via pip
deps-test:
	$(PIP) install -r requirements_test.txt

# Install
install:
	$(PIP) install .

# Build docker image
docker:
	docker build -t $(DOCKER_TAG) .

.PHONY: test install deps deps-ubuntu deps deps-test help
# Run test
test: test/assets
	# declare -p HTTP_PROXY
	$(PYTHON) -m pytest test $(PYTEST_ARGS)

test-cli: test/assets
	pip install -e .
	rm -fv test-workspace
	cp -rv test/assets/kant_aufklaerung_1784 test-workspace
	cd test-workspace && \
		ocrd-tesserocr-segment-region -m mets.xml -I OCR-D-IMG -O OCR-D-SEG-BLOCK ; \
		ocrd-tesserocr-segment-line -m mets.xml -I OCR-D-SEG-BLOCK -O OCR-D-SEG-LINE ; \
		ocrd-tesserocr-recognize -m mets.xml -I OCR-D-SEG-LINE -O OCR-D-TESS-OCR


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
