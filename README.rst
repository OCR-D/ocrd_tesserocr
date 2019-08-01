ocrd_tesserocr
==============

    Crop, deskew, segment into regions / lines / words, or recognize with tesserocr

.. image:: https://circleci.com/gh/OCR-D/ocrd_tesserocr.svg?style=svg
    :target: https://circleci.com/gh/OCR-D/ocrd_tesserocr

.. image:: https://img.shields.io/pypi/v/ocrd_tesserocr.svg
    :target: https://pypi.org/project/ocrd_tesserocr/

.. image:: https://codecov.io/gh/OCR-D/ocrd_tesserocr/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/OCR-D/ocrd_tesserocr

.. image:: https://img.shields.io/docker/automated/ocrd/tesserocr.svg
    :target: https://hub.docker.com/r/ocrd/tesserocr/tags/
    :alt: Docker Automated build

Introduction
------------

This offers `OCR-D`_ compliant workspace processors for (much of) the functionality of `Tesseract`_ via its Python API wrapper `tesserocr`_ . (Each processor is a step in the OCR-D functional model, and can be replaced with an alternative implementation. Data is represented within METS/PAGE.)

This includes image preprocessing (cropping, binarization, deskewing), layout analysis (region, line, word segmentation) and OCR proper. Most processors can operate on different levels of the PAGE hierarchy, depending on the workflow configuration. Image results are referenced (read and written) via ``AlternativeImage``, text results via ``TextEquiv``, deskewing via ``@orientation``, cropping via ``Border`` and segmentation via ``Region`` / ``TextLine`` / ``Word`` elements with ``Coords/@points``.

.. _OCR-D: https://ocr-d.github.io
.. _Tesseract: https://github.com/tesseract-ocr
.. _tesserocr: https://github.com/sirfz/tesserocr


Installation
------------

Required ubuntu packages:

* Tesseract headers (``libtesseract-dev``)
* Some tesseract language models (``tesseract-ocr-{eng,deu,frk,...}`` or script models (``tesseract-ocr-script-{latn,frak,...}``)
* Leptonica headers (``libleptonica-dev``)

::

    make deps-ubuntu # or manually
    make deps # or pip install -r requirements
    make install # or pip install .

If tesserocr fails to compile with an error:::

    $PREFIX/include/tesseract/unicharset.h:241:10: error: ‘string’ does not name a type; did you mean ‘stdin’? 
           static string CleanupString(const char* utf8_str) {
                  ^~~~~~
                  stdin

This is due to some inconsistencies in the installed tesseract C headers (fix expected for next Ubuntu upgrade, already fixed for Debian).
Replace ``string`` with ``std::string`` in ``$PREFIX/include/tesseract/unicharset.h:265:5:`` and ``$PREFIX/include/tesseract/unichar.h:164:10:`` ff.

If tesserocr fails with an error about ``LSTM``/``CUBE``, you have a
mismatch between tesseract header/data/pkg-config versions. ``apt policy
libtesseract-dev`` lists the apt-installable versions, keep it consistent. Make
sure there are no spurious pkg-config artifacts, e.g. in
``/usr/local/lib/pkgconfig/tesseract.pc``. The same goes for language models.


Usage
-----

See docstrings and in the individual processors and `ocrd-tool.json`_ descriptions.

.. _ocrd-tool.json: ocrd_tesserocr/ocrd-tool.json

Available processors are:

- `ocrd-tesserocr-crop`_
- `ocrd-tesserocr-deskew`_
- `ocrd-tesserocr-binarize`_
- `ocrd-tesserocr-segment-region`_
- `ocrd-tesserocr-segment-line`_
- `ocrd-tesserocr-segment-word`_
- `ocrd-tesserocr-recognize`_

.. _`ocrd-tesserocr-crop`: ocrd_tesserocr/crop.py
.. _`ocrd-tesserocr-deskew`: ocrd_tesserocr/deskew.py
.. _`ocrd-tesserocr-binarize`: ocrd_tesserocr/binarize.py
.. _`ocrd-tesserocr-segment-region`: ocrd_tesserocr/segment_region.py
.. _`ocrd-tesserocr-segment-line`: ocrd_tesserocr/segment_line.py
.. _`ocrd-tesserocr-segment-word`: ocrd_tesserocr/segment_word.py
.. _`ocrd-tesserocr-recognize`: ocrd_tesserocr/recognize.py


Testing
-------

::

    make test

This downloads some test data from <https://github.com/OCR-D/assets> under ``repo/assets``, and runs some basic test of the Python API as well as the CLIs.

Set ``PYTEST_ARGS="-s --verbose"`` to see log output (``-s``) and individual test results (``--verbose``).
