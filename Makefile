export

SHELL = /bin/bash
PYTHON = python3
PIP = pip3
LOG_LEVEL = INFO
PYTHONIOENCODING=utf8
LC_ALL = C.UTF-8
LANG = C.UTF-8
ifdef VIRTUAL_ENV
	TESSERACT_PREFIX = $(VIRTUAL_ENV)
else
	TESSERACT_PREFIX = /usr/local
endif

ifeq ($(PKG_CONFIG_PATH),)
PKG_CONFIG_PATH := $(TESSERACT_PREFIX)/lib/pkgconfig
else
PKG_CONFIG_PATH := $(TESSERACT_PREFIX)/lib/pkgconfig:$(PKG_CONFIG_PATH)
endif
export PKG_CONFIG_PATH

export

# pytest args. Set to '-s' to see log output during test execution, '--verbose' to see individual tests. Default: '$(PYTEST_ARGS)'
PYTEST_ARGS =

# Docker container tag
DOCKER_TAG = 'ocrd/tesserocr'

help:
	@echo ""
	@echo "  Targets"
	@echo ""
	@echo "    deps-ubuntu       Install system dependencies in an Ubuntu/Debian Linux"
	@echo "    install-tesseract Compile and install Tesseract"
	@echo "    install-tesseract-training Compile and install training utilities for Tesseract"
	@echo "    install-tesserocr Compile and install Tesserocr"
	@echo "    deps              Install Python dependencies for install via pip"
	@echo "    install           Install this package via pip"
	@echo "    deps-test         Install Python deps for test via pip"
	@echo "    test              Run unit tests"
	@echo "    coverage          Run unit tests and determine test coverage"
	@echo "    test-cli          Test the command line tools"
	@echo "    test/assets       Setup test assets"
	@echo "    repo/assets       Clone OCR-D/assets to ./repo/assets"
	@echo "    repo/tesseract    Checkout Tesseract ./repo/tesseract"
	@echo "    repo/tesserocr    Checkout Tesserocr to ./repo/tesserocr"
	@echo "    docker            Build docker image"
	@echo "    assets-clean      Remove symlinks in test/assets"
	@echo ""
	@echo "  Variables"
	@echo ""
	@echo "    PYTEST_ARGS     pytest args. Set to '-s' to see log output during test execution, '--verbose' to see individual tests. [$(PYTEST_ARGS)]"
	@echo "    DOCKER_TAG      Docker container tag [$(DOCKER_TAG)]"
	@echo "    TESSDATA_PREFIX search path for recognition models (overriding Tesseract compile-time default) [$(TESSDATA_PREFIX)]"

# Dependencies for deployment in an Ubuntu/Debian Linux
# (lib*-dev merely for building Tesseract and tesserocr from sources)
deps-ubuntu:
	apt-get update && apt-get install -y --no-install-recommends \
		apt-utils \
		build-essential \
		g++ \
		git \
		python3 \
		python3-pip \
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

# Install Python deps for install via pip
deps:
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

# Install Python deps for test via pip
deps-test:
	$(PIP) install -r requirements_test.txt

# Build docker image
docker:
	docker build \
	--build-arg VCS_REF=$$(git rev-parse --short HEAD) \
	--build-arg BUILD_DATE=$$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
	-t $(DOCKER_TAG) .

install-tesserocr: repo/tesserocr
	$(PIP) install ./$<

install-tesseract: $(TESSERACT_PREFIX)/bin/tesseract

install-tesseract-training: $(TESSERACT_PREFIX)/bin/lstmtraining

$(TESSERACT_PREFIX)/bin/tesseract: build_tesseract/Makefile
	$(MAKE) -C build_tesseract install
	if [[ "$(TESSERACT_PREFIX)" = "/usr"* ]]; then ldconfig; fi

$(TESSERACT_PREFIX)/bin/lstmtraining: build_tesseract/Makefile
	$(MAKE) -C build_tesseract training-install

build_tesseract/Makefile: repo/tesseract/Makefile.in
	mkdir -p $(@D)
	cd $(@D) && $(CURDIR)/repo/tesseract/configure \
				--prefix=$(TESSERACT_PREFIX) \
				--disable-openmp \
				--disable-shared \
				'CXXFLAGS=-g -O2 -fno-math-errno -Wall -Wextra -Wpedantic -fPIC'

repo/tesseract/Makefile.in: repo/tesseract
	cd $<; ./autogen.sh

repo/tesserocr repo/tesseract:
	git submodule sync $@
	git submodule update --init $@

# Install this package
install: deps
	$(PIP) install .

# Run unit tests
test: test/assets deps-test
	@# declare -p HTTP_PROXY
	#$(PYTHON) -m pytest -n auto --continue-on-collection-errors test $(PYTEST_ARGS)
	# workaround for pytest-xdist not isolating setenv calls in click.CliRunner from each other:
	$(PYTHON) -m pytest --continue-on-collection-errors test/test_cli.py $(PYTEST_ARGS)
	$(PYTHON) -m pytest -n auto --continue-on-collection-errors test/test_{segment_{region,line,word},recognize}.py $(PYTEST_ARGS)

# Run unit tests and determine test coverage
coverage: deps-test
	coverage erase
	make test PYTHON="coverage run"
	coverage report
	coverage html

# Test the command line tools
test-cli: test/assets
	$(PIP) install -e .
	rm -rfv test/workspace
	cp -rv test/assets/kant_aufklaerung_1784 test/workspace
	ocrd resmgr download ocrd-tesserocr-recognize eng.traineddata
	ocrd resmgr download ocrd-tesserocr-recognize deu.traineddata
	cd test/workspace/data && \
		ocrd-tesserocr-segment-region -l DEBUG -I OCR-D-IMG -O OCR-D-SEG-REGION && \
		ocrd-tesserocr-segment-line   -l DEBUG -I OCR-D-SEG-REGION -O OCR-D-SEG-LINE && \
		ocrd-tesserocr-recognize      -l DEBUG -I OCR-D-SEG-LINE -O OCR-D-TESS-OCR -P model deu

.PHONY: test test-cli install deps deps-ubuntu deps-test help

#
# Assets
#

# Setup test assets (copy repo/assets)
# FIXME remove/update if already present
test/assets: repo/assets
	mkdir -p $@
	cp -r -t $@ repo/assets/data/*

# Clone OCR-D/assets to ./repo/assets
# FIXME does not work if already checked out
# FIXME should be a proper (VCed) submodule
repo/assets:
	mkdir -p $(dir $@)
	git clone https://github.com/OCR-D/assets "$@"

.PHONY: clean
clean: assets-clean tesseract-clean

tesseract-clean:
	rm -rf $(CURDIR)/build_tesseract
	cd repo/tesseract; make distclean

.PHONY: assets-clean
# Remove symlinks in test/assets
assets-clean:
	rm -rf test/assets
