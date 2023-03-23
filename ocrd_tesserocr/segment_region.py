from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd_validators import ParameterValidator

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment-region'
BASE_TOOL = 'ocrd-tesserocr-recognize'

class TesserocrSegmentRegion(TesserocrRecognize):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('ocrd_tool', OCRD_TOOL['tools'][TOOL])
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.parameter['overwrite_segments'] = self.parameter['overwrite_regions']
            del self.parameter['overwrite_regions']
            self.parameter['segmentation_level'] = "region"
            self.parameter['textequiv_level'] = "region"
            self.parameter['block_polygons'] = self.parameter['crop_polygons']
            del self.parameter['crop_polygons']
            # add default params
            assert ParameterValidator(OCRD_TOOL['tools'][BASE_TOOL]).validate(self.parameter).is_valid
            self.logger = getLogger('processor.TesserocrSegmentRegion')

TesserocrSegmentRegion.process.__doc__ = """Performs region segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        and remove any existing Region and ReadingOrder elements
        (unless ``overwrite_regions`` is False).
        
        Set up Tesseract to detect blocks, and add each one to the page
        as a region according to BlockType at the detected coordinates.
        If ``find_tables`` is True, try to detect table blocks and add them
        as (atomic) TableRegion.
        
        If ``crop_polygons`` is True, then query polygon outlines instead of
        bounding boxes from Tesseract for each region. (This is more precise,
        but due to some path representation errors does not always yield
        accurate/valid polygons.)
        
        If ``shrink_polygons``, then query Tesseract for all symbols/glyphs
        of each segment and calculate the convex hull for them.
        Annotate the resulting polygon instead of the coarse bounding box.
        (This is more precise and helps avoid overlaps between neighbours, especially
        when not segmenting all levels at once.)
        
        Produce a new output file by serialising the resulting hierarchy.
        """
