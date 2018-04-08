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
		libtesseract-dev \
		libleptonica-dev \
		tesseract-ocr-eng

# Install python deps via pip
deps-pip:
	$(PIP) install -r requirements.txt

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
