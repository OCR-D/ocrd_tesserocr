from __future__ import absolute_import

import os.path
import io

import numpy as np

from ocrd_models import OcrdExif
from ocrd_utils import (
    getLogger,
    coordinates_of_segment,
    xywh_from_points,
    polygon_from_points,
    image_from_polygon,
    crop_image,
)

LOG = getLogger('') # to be refined by importer


