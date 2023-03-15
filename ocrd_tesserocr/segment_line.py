from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd_validators import ParameterValidator

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment-line'
BASE_TOOL = 'ocrd-tesserocr-recognize'

class TesserocrSegmentLine(TesserocrRecognize):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('ocrd_tool', OCRD_TOOL['tools'][TOOL])
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.parameter['overwrite_segments'] = self.parameter['overwrite_lines']
            del self.parameter['overwrite_lines']
            self.parameter['segmentation_level'] = "line"
            self.parameter['textequiv_level'] = "line"
            # add default params
            assert ParameterValidator(OCRD_TOOL['tools'][BASE_TOOL]).validate(self.parameter).is_valid
            self.logger = getLogger('processor.TesserocrSegmentLine')

TesserocrSegmentLine.process.__doc__ = """Performs (text) line segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the (text) region level,
        and remove any existing TextLine elements (unless ``overwrite_lines``
        is False).
        
        Set up Tesseract to detect lines, and add each one to the region
        at the detected coordinates.
        
        If ``shrink_polygons``, then during segmentation (on any level), query Tesseract
        for all symbols/glyphs of each segment and calculate the convex hull for them.
        Annotate the resulting polygon instead of the coarse bounding box.
        (This is more precise and helps avoid overlaps between neighbours, especially
        when not segmenting all levels at once.)
        
        Produce a new output file by serialising the resulting hierarchy.
        """
