from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd_validators import ParameterValidator

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment'
BASE_TOOL = 'ocrd-tesserocr-recognize'

class TesserocrSegment(TesserocrRecognize):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('ocrd_tool', OCRD_TOOL['tools'][TOOL])
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.parameter['overwrite_segments'] = True
            self.parameter['segmentation_level'] = "region"
            self.parameter['textequiv_level'] = "none"
            # add default params
            assert ParameterValidator(OCRD_TOOL['tools'][BASE_TOOL]).validate(self.parameter).is_valid
            self.logger = getLogger('processor.TesserocrSegment')

TesserocrSegment.process.__doc__ = """Performs region and line segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        and remove any existing Region and ReadingOrder elements.
        
        Set up Tesseract to detect blocks, and add each one to the page
        as a region according to BlockType at the detected coordinates
        (bounding boxes).
        
        If ``find_tables`` is True, try to detect table blocks and add them
        as TableRegion, then query the page iterator for paragraphs and add
        them as TextRegion cells.
        
        If ``block_polygons``, then query Tesseract for polygon outlines
        instead of bounding boxes for each region.
        (This is more precise, but due to some path representation errors does
        not always yield accurate/valid polygons.)
        
        If ``shrink_polygons``, then query Tesseract for all symbols/glyphs
        of each segment and calculate the convex hull for them.
        Annotate the resulting polygon instead of the coarse bounding box.
        (This is more precise and helps avoid overlaps between neighbours, especially
        when not segmenting all levels at once.)
        
        If ``sparse_text``, then attempt to find single-line text blocks only,
        in no particular order.
        
        Next, query the page iterator for text lines inside the text regions,
        and add each one to the region according to the detected coordinates
        (bounding boxes).
        
        Finally, query the page iterator for words inside the text lines,
        and add each one to the line according to the detected coordinates
        (bounding boxes).
        
        Produce a new output file by serialising the resulting hierarchy.
        """
