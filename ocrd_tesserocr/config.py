import os
import tesserocr
TESSDATA_PREFIX = os.environ['TESSDATA_PREFIX'] if 'TESSDATA_PREFIX' in os.environ else tesserocr.get_languages()[0]
