import os
import json
from os.path import join
from pkg_resources import resource_string

import tesserocr

from ocrd.resource_manager import OcrdResourceManager

location = OcrdResourceManager().default_resource_dir
MODEL_LOCATION = join(location, 'ocrd-tesserocr-recognize')
MODEL_LOCATION_CROP = join(location, 'ocrd-tesserocr-crop')

OCRD_TOOL = json.loads(resource_string(__name__, 'ocrd-tool.json').decode('utf8'))
