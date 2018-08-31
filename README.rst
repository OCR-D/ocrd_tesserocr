ocrd_tesserocr
==============

    Segment region, line, recognize with tesserocr

.. image:: https://travis-ci.org/OCR-D/ocrd_tesserocr.svg?branch=master
    :target: https://travis-ci.org/OCR-D/ocrd_tesserocr

.. image:: https://img.shields.io/pypi/v/ocrd_tesserocr.svg
    :target: https://pypi.org/project/ocrd_tesserocr/

.. image:: https://img.shields.io/docker/automated/ocrd/tesserocr.svg
    :target: https://hub.docker.com/r/ocrd/tesserocr/tags/
    :alt: Docker Automated build


Installation
------------

Required ubuntu packages:

* Tesseract headers (``libtesseract-dev``)
* Some tesseract language models (``tesseract-ocr-{eng,deu,frk,...}`` or script models (``tesseract-ocr-script-{latn,frak,...}``)
* Leptonica headers (``libleptonica-dev``)

::

    pip install -r requirements
    pip install .

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
