# pylint: disable=unused-import

import os
import sys
from unittest import TestCase, skip, main # pylint: disable=unused-import

from test.assets import assets

PWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(PWD + '/../ocrd')
