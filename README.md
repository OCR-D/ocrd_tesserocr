# ocrd_tesserocr

> Crop, deskew, segment into regions / tables / lines / words, or recognize with tesserocr

[![image](https://circleci.com/gh/OCR-D/ocrd_tesserocr.svg?style=svg)](https://circleci.com/gh/OCR-D/ocrd_tesserocr)
[![image](https://img.shields.io/pypi/v/ocrd_tesserocr.svg)](https://pypi.org/project/ocrd_tesserocr/)
[![image](https://codecov.io/gh/OCR-D/ocrd_tesserocr/branch/master/graph/badge.svg)](https://codecov.io/gh/OCR-D/ocrd_tesserocr)
[![Docker Automated build](https://img.shields.io/docker/automated/ocrd/tesserocr.svg)](https://hub.docker.com/r/ocrd/tesserocr/tags/)

## Introduction

This package offers [OCR-D](https://ocr-d.de/en/spec) compliant [workspace processors](https://ocr-d.de/en/spec/cli) for (much of) the functionality of [Tesseract](https://github.com/tesseract-ocr) via its Python API wrapper [tesserocr](https://github.com/sirfz/tesserocr). (Each processor is a parameterizable step in a configurable [workflow](https://ocr-d.de/en/workflows) of the [OCR-D functional model](https://ocr-d.de/en/about). There are usually various alternative processor implementations for each step. Data is represented with [METS](https://ocr-d.de/en/spec/mets) and [PAGE](https://ocr-d.de/en/spec/page).)

It includes image preprocessing (cropping, binarization, deskewing), layout analysis (region, table, line, word segmentation), script identification, font style recognition and text recognition. 

Most processors can operate on different levels of the PAGE hierarchy, depending on the workflow configuration. In PAGE, image results are referenced (read and written) via `AlternativeImage`, text results via `TextEquiv`, font attributes via `TextStyle`, script via `@primaryScript`, deskewing via `@orientation`, cropping via `Border` and segmentation via `Region` / `TextLine` / `Word` elements with `Coords/@points`.

## Installation

### With docker

This is the best option if you want to run the software in a container.

You need to have [Docker](https://docs.docker.com/install/linux/docker-ce/ubuntu/)


    docker pull ocrd/tesserocr


To run with docker:


    docker run -v path/to/workspaces:/data ocrd/tesserocr ocrd-tesserocrd-crop ...


### From PyPI and Tesseract provided by system

If your operating system / distribution already provides Tesseract 4.1
or newer, then just install its development package:

    # on Debian / Ubuntu:
    sudo apt install libtesseract-dev

Otherwise, recent Tesseract packages for Ubuntu are available via PPA
[alex-p](https://launchpad.net/~alex-p/+archive/ubuntu/tesseract-ocr-devel),
which has up-to-date builds of Tesseract and its dependencies:


    # on Debian / Ubuntu
    sudo add-apt-repository ppa:alex-p/tesseract-ocr
    sudo apt-get update
    sudo apt install libtesseract-dev

Once Tesseract is available, just install ocrd_tesserocr from PyPI server:


    pip install ocrd_tesserocr

We strongly recommend setting up a
[venv](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/) first.


### From git

Use this option if there is no suitable prebuilt version of Tesseract available
on your system, or you want to change the source code or install the latest, unpublished changes.

    git clone https://github.com/OCR-D/ocrd_tesserocr
    cd ocrd_tesserocr
    # install Tesseract:
    sudo make deps-ubuntu # system dependencies just for the build
    make deps
    # install tesserocr and ocrd_tesserocr:
    make install

We strongly recommend setting up a
[venv](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/) first.


## Models

Tesseract comes with synthetically trained models for languages (`tesseract-ocr-{eng,deu,deu_latf,...}`
or scripts (`tesseract-ocr-script-{latn,frak,...}`). In addition, various models
[trained](https://github.com/tesseract-ocr/tesstrain) on scan data are available from the community.

Since all OCR-D processors must resolve file/data resources
in a [standardized way](https://ocr-d.de/en/spec/cli#processor-resources),
and we want to stay interoperable with standalone Tesseract
(which uses a single compile-time `tessdata` directory),
`ocrd-tesserocr-recognize` expects the recognition models to be installed
in its [module](https://ocr-d.de/en/spec/ocrd_tool#file-parameters) **resource location** only.
The `module` location is determined by the underlying Tesseract installation
(compile-time `tessdata` directory, or run-time `$TESSDATA_PREFIX` environment variable).
Other resource locations (data/system/cwd) will be ignored, and should not be used
when installing models with the **Resource Manager** (`ocrd resmgr download`).

To see the `module` resource location of your installation:

    ocrd-tesserocr-recognize -D

For a full description of available commands for resource management, see:

    ocrd resmgr --help
    ocrd resmgr list-available --help
    ocrd resmgr download --help
    ocrd resmgr list-installed --help

> **Note**: 
> (In previous versions, the resource locations of standalone Tesseract and the OCR-D wrapper were different.
> If you already have models under `$XDG_DATA_HOME/ocrd-resources/ocrd-tesserocr-recognize`,
> usually `~/.local/share/ocrd-resources/ocrd-tesserocr-recognize`, then consider moving them
> to the new default under `ocrd-tesserocr-recognize -D`,
> usually `/usr/share/tesseract-ocr/4.00/tessdata`, _or_ alternatively overriding the module directory
> by setting `TESSDATA_PREFIX=$XDG_DATA_HOME/ocrd-resources/ocrd-tesserocr-recognize` in the environment.)

Cf. [OCR-D model guide](https://ocr-d.de/en/models).

Models always use the filename suffix `.traineddata`, but are just loaded by their basename.
You will need **at least** `eng` and `osd` installed (even for segmentation and deskewing),
probably also `Latin` and `Fraktur` etc. So to get minimal models, do:

	ocrd resmgr download ocrd-tesserocr-recognize eng.traineddata
	ocrd resmgr download ocrd-tesserocr-recognize osd.traineddata

(This will already be installed if using the Docker or git installation option.)

As of v0.13.1, you can configure `ocrd-tesserocr-recognize` to select models **dynamically** segment by segment,
either via custom conditions on the PAGE-XML annotation (presented as XPath rules),
or by automatically choosing the model with highest confidence.

## Usage

For details, see docstrings in the individual processors
and [ocrd-tool.json](ocrd_tesserocr/ocrd-tool.json) descriptions,
or simply `--help`.

Available [OCR-D processors](https://ocr-d.de/en/spec/cli) are:

- [ocrd-tesserocr-crop](ocrd_tesserocr/crop.py)
  (simplistic)
  - sets `Border` of pages and adds `AlternativeImage` files to the output fileGrp
- [ocrd-tesserocr-deskew](ocrd_tesserocr/deskew.py)
  (for skew and orientation; mind `operation_level`)
  - sets `@orientation` of regions or pages and adds `AlternativeImage` files to the output fileGrp
- [ocrd-tesserocr-binarize](ocrd_tesserocr/binarize.py)
  (Otsu – not recommended, unless already binarized and using `tiseg`)
  - adds `AlternativeImage` files to the output fileGrp
- [ocrd-tesserocr-recognize](ocrd_tesserocr/recognize.py)
  (optionally including segmentation; mind `segmentation_level` and `textequiv_level`)
  - adds `TextRegion`s, `TableRegion`s, `ImageRegion`s, `MathsRegion`s, `SeparatorRegion`s,
    `NoiseRegion`s, `ReadingOrder` and `AlternativeImage` to `Page` and sets their `@orientation` (optionally)
  - adds `TextRegion`s to `TableRegion`s and sets their `@orientation` (optionally)
  - adds `TextLine`s to `TextRegion`s (optionally)
  - adds `Word`s to `TextLine`s (optionally)
  - adds `Glyph`s to `Word`s (optionally)
  - adds `TextEquiv`
- [ocrd-tesserocr-segment](ocrd_tesserocr/segment.py)
  (all-in-one segmentation – recommended; delegates to `recognize`)
  - adds `TextRegion`s, `TableRegion`s, `ImageRegion`s, `MathsRegion`s, `SeparatorRegion`s,
    `NoiseRegion`s, `ReadingOrder` and `AlternativeImage` to `Page` and sets their `@orientation`
  - adds `TextRegion`s to `TableRegion`s and sets their `@orientation`
  - adds `TextLine`s to `TextRegion`s
  - adds `Word`s to `TextLine`s
  - adds `Glyph`s to `Word`s
- [ocrd-tesserocr-segment-region](ocrd_tesserocr/segment_region.py)
  (only regions – with overlapping bboxes; delegates to `recognize`)
  - adds `TextRegion`s, `TableRegion`s, `ImageRegion`s, `MathsRegion`s, `SeparatorRegion`s,
    `NoiseRegion`s and `ReadingOrder` to `Page` and sets their `@orientation`
- [ocrd-tesserocr-segment-table](ocrd_tesserocr/segment_table.py)
  (only table cells; delegates to `recognize`)
  - adds `TextRegion`s to `TableRegion`s
- [ocrd-tesserocr-segment-line](ocrd_tesserocr/segment_line.py)
  (only lines – from overlapping regions; delegates to `recognize`)
  - adds `TextLine`s to `TextRegion`s
- [ocrd-tesserocr-segment-word](ocrd_tesserocr/segment_word.py)
  (only words; delegates to `recognize`)
  - adds `Word`s to `TextLine`s
- [ocrd-tesserocr-fontshape](ocrd_tesserocr/fontshape.py)
  (only text style – via Tesseract 3 models)
  - adds `TextStyle` to `Word`s

The text region `@type`s detected are (from Tesseract's [PolyBlockType](https://github.com/tesseract-ocr/tesseract/blob/11297c983ec7f5c9765d7fa4faa48f5150cf2d38/include/tesseract/publictypes.h#L52-L69)):
- `paragraph`: normal block (aligned with others in the column)
- `floating`: unaligned block (`is in a cross-column pull-out region`)
- `heading`: block that `spans more than one column`
- `caption`: block for `text that belongs to an image`

If you are unhappy with these choices, then consider post-processing
with a dedicated custom processor in Python, or by modifying the PAGE files directly
(e.g. `xmlstarlet ed --inplace -u '//pc:TextRegion/@type[.="floating"]' -v paragraph filegrp/*.xml`).

All segmentation is currently done as **bounding boxes** only by default,
i.e. without precise polygonal outlines. For dense page layouts this means
that neighbouring regions and neighbouring text lines may overlap a lot.
If this is a problem for your workflow, try post-processing like so:
- after line segmentation: use `ocrd-cis-ocropy-resegment` for polygonalization,
  or `ocrd-cis-ocropy-clip` on the line level
- after region segmentation: use `ocrd-segment-repair` with `plausibilize`
  (and `sanitize` after line segmentation)

It also means that Tesseract should be allowed to segment across multiple hierarchy levels
at once, to avoid introducing inconsistent/duplicate text line assignments in text regions,
or word assignments in text lines. Hence,
- prefer `ocrd-tesserocr-recognize` with `segmentation_level=region`  
  over `ocrd-tesserocr-segment` followed by `ocrd-tesserocr-recognize`,  
  if you want to do all in one with Tesseract,
- prefer `ocrd-tesserocr-recognize` with `segmentation_level=line`  
  over `ocrd-tesserocr-segment-line` followed by `ocrd-tesserocr-recognize`,  
  if you want to do everything but region segmentation with Tesseract,
- prefer `ocrd-tesserocr-segment` over `ocrd-tesserocr-segment-region`  
  followed by (`ocrd-tesserocr-segment-table` and) `ocrd-tesserocr-segment-line`,  
  if you want to do everything but recognition with Tesseract.

However, you can also run `ocrd-tesserocr-segment*` and `ocrd-tesserocr-recognize`
with `shrink_polygons=True` to get **polygons** by post-processing each segment,
shrinking to the convex hull of all its symbol outlines.

## Testing


    make test


This downloads some test data from https://github.com/OCR-D/assets under `repo/assets`,
and runs some basic test of the Python API as well as the CLIs.

Set `PYTEST_ARGS="-s --verbose"` to see log output (`-s`) and individual test results (`--verbose`).
