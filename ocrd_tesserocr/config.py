import os
import json
from os.path import join
from pkg_resources import resource_string

OCRD_TOOL = json.loads(resource_string(__name__, 'ocrd-tool.json').decode('utf8'))
