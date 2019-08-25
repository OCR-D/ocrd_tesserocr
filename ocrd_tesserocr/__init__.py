import locale
# Circumvent tesseract-ocr issue #1670
# (which cannot be done on command line
# because Click requires an UTF-8 locale
# in Python 3).
# Setting the locale is no longer needed with
# Tesseract 4.1.0, 5.0.0-alpha or newer versions.
# Setting the locale fails with Python 3.7 on macOS
# so try running without a special locale if there
# is an exception.
# pylint: disable=wrong-import-position
try:
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')
except locale.Error:
    pass

from .recognize import TesserocrRecognize
from .segment_word import TesserocrSegmentWord
from .segment_line import TesserocrSegmentLine
from .segment_region import TesserocrSegmentRegion
from .crop import TesserocrCrop
from .deskew import TesserocrDeskew
from .binarize import TesserocrBinarize
