import os
import json
from os.path import join
from pkg_resources import resource_string

import tesserocr

from ocrd.resource_manager import OcrdResourceManager

def get_tessdata_path():
    if 'TESSDATA_PREFIX' in os.environ:
        return os.environ['TESSDATA_PREFIX']
    return join(OcrdResourceManager().default_resource_dir, 'ocrd-tesserocr-recognize')

OCRD_TOOL = json.loads(resource_string(__name__, 'ocrd-tool.json').decode('utf8'))
