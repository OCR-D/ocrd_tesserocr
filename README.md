# ocrd_tesserocr

> Crop, deskew, segment into regions / lines / words, or recognize with tesserocr

[![image](https://circleci.com/gh/OCR-D/ocrd_tesserocr.svg?style=svg)](https://circleci.com/gh/OCR-D/ocrd_tesserocr)
[![image](https://img.shields.io/pypi/v/ocrd_tesserocr.svg)](https://pypi.org/project/ocrd_tesserocr/)
[![image](https://codecov.io/gh/OCR-D/ocrd_tesserocr/branch/master/graph/badge.svg)](https://codecov.io/gh/OCR-D/ocrd_tesserocr)
[![Docker Automated build](https://img.shields.io/docker/automated/ocrd/tesserocr.svg)](https://hub.docker.com/r/ocrd/tesserocr/tags/)

## Introduction

This offers [OCR-D](https://ocr-d.github.io) compliant workspace processors for (much of) the functionality of [Tesseract](https://github.com/tesseract-ocr) via its Python API wrapper [tesserocr](https://github.com/sirfz/tesserocr) . (Each processor is a step in the OCR-D functional model, and can be replaced with an alternative implementation. Data is represented within METS/PAGE.)

This includes image preprocessing (cropping, binarization, deskewing), layout analysis (region, line, word segmentation) and OCR proper. Most processors can operate on different levels of the PAGE hierarchy, depending on the workflow configuration. Image results are referenced (read and written) via `AlternativeImage`, text results via `TextEquiv`, deskewing via `@orientation`, cropping via `Border` and segmentation via `Region` / `TextLine` / `Word` elements with `Coords/@points`.

## Installation

### Required ubuntu packages:

- Tesseract headers (`libtesseract-dev`)
- Some tesseract language models (`tesseract-ocr-{eng,deu,frk,...}` or script models (`tesseract-ocr-script-{latn,frak,...}`)
- Leptonica headers (`libleptonica-dev`)

### From PyPI

This is the best option if you want to use the stable, released version.

---

**NOTE**

ocrd_tesserocr requires **Tesseract >= 4.1.0**. The Tesseract packages
bundled with **Ubuntu < 19.10** are too old. If you are on Ubuntu 18.04 LTS,
please enable [Alexander Pozdnyakov PPA](https://launchpad.net/~alex-p/+archive/ubuntu/tesseract-ocr) which
has up-to-date builds of Tesseract and its dependencies:

```sh
sudo add-apt-repository ppa:alex-p/tesseract-ocr
sudo apt-get update
```

---

```sh
sudo apt-get install git python3 python3-pip libtesseract-dev libleptonica-dev tesseract-ocr-eng tesseract-ocr wget
pip install ocrd_tesserocr
```

### With docker

This is the best option if you want to run the software in a container.

You need to have [Docker](https://docs.docker.com/install/linux/docker-ce/ubuntu/)

```sh
docker pull ocrd/tesserocr
```

### From git 

This is the best option if you want to change the source code or install the latest, unpublished changes.

We strongly recommend to use [venv](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).

```sh
git clone https://github.com/OCR-D/ocrd_tesserocr
cd ocrd_tesserocr
make deps-ubuntu # or manually with apt-get
make deps        # or pip install -r requirements
make install     # or pip install .
```

## Usage

See docstrings and in the individual processors and [ocrd-tool.json](ocrd_tesserocr/ocrd-tool.json) descriptions.

Available processors are:

- [ocrd-tesserocr-crop](ocrd_tesserocr/crop.py)
- [ocrd-tesserocr-deskew](ocrd_tesserocr/deskew.py)
- [ocrd-tesserocr-binarize](ocrd_tesserocr/binarize.py)
- [ocrd-tesserocr-segment-region](ocrd_tesserocr/segment_region.py)
- [ocrd-tesserocr-segment-line](ocrd_tesserocr/segment_line.py)
- [ocrd-tesserocr-segment-word](ocrd_tesserocr/segment_word.py)
- [ocrd-tesserocr-recognize](ocrd_tesserocr/recognize.py)

## Testing

To run with docker:

```
docker run ocrd/tesserocr ocrd-tesserocrd-crop ...
```

## Testing

```sh
make test
```

This downloads some test data from https://github.com/OCR-D/assets under `repo/assets`, and runs some basic test of the Python API as well as the CLIs.

Set `PYTEST_ARGS="-s --verbose"` to see log output (`-s`) and individual test results (`--verbose`).

## Development

Latest changes that require pre-release of [ocrd >= 2.0.0](https://github.com/OCR-D/core/tree/edge) are kept in branch [`edge`](https://github.com/OCR-D/ocrd_tesserocr/tree/edge).
