import locale
# circumvent tesseract-ocr issue #1670
# (which cannot be done on command line
# because Click requires an UTF-8 locale
# in Python 3):
# pylint: disable=wrong-import-position
locale.setlocale(locale.LC_ALL, 'C.UTF-8')

from .recognize import TesserocrRecognize
from .segment_word import TesserocrSegmentWord
from .segment_line import TesserocrSegmentLine
from .segment_region import TesserocrSegmentRegion
from .crop import TesserocrCrop
