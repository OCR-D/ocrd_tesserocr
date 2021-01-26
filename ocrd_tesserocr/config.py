import os
import json
from os.path import join
from pkg_resources import resource_string

import tesserocr

from ocrd.resource_manager import OcrdResourceManager

if 'TESSDATA_PREFIX' in os.environ:
    TESSDATA_PREFIX = os.environ['TESSDATA_PREFIX']
else:
    location = OcrdResourceManager().default_resource_dir
    TESSDATA_PREFIX = join(location, 'ocrd-tesserocr-recognize')

OCRD_TOOL = json.loads(resource_string(__name__, 'ocrd-tool.json').decode('utf8'))
