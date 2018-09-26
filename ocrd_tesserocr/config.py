import os
import json
from pkg_resources import resource_string

import locale
locale.setlocale(locale.LC_ALL, 'C') # circumvent tesseract-ocr issue 1670 (which cannot be done on command line because Click requires an UTF-8 locale in Python 3)
import tesserocr

TESSDATA_PREFIX = os.environ['TESSDATA_PREFIX'] if 'TESSDATA_PREFIX' in os.environ else tesserocr.get_languages()[0]

OCRD_TOOL = json.loads(resource_string(__name__, 'ocrd-tool.json').decode('utf8'))
