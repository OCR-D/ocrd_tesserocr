from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd import Processor

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment-line'

class TesserocrSegmentLine(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super().__init__(*args, **kwargs)

        if hasattr(self, 'workspace'):
            recognize_kwargs = {**kwargs}
            recognize_kwargs.pop('dump_json', None)
            recognize_kwargs.pop('show_help', None)
            recognize_kwargs.pop('show_version', None)
            recognize_kwargs['parameter'] = self.parameter
            recognize_kwargs['parameter']['overwrite_segments'] = self.parameter['overwrite_lines']
            del recognize_kwargs['parameter']['overwrite_lines']
            recognize_kwargs['parameter']['segmentation_level'] = "line"
            recognize_kwargs['parameter']['textequiv_level'] = "line"
            self.recognizer = TesserocrRecognize(self.workspace, **recognize_kwargs)
            self.recognizer.logger = getLogger('processor.TesserocrSegmentLine')

    def process(self):
        """Performs (text) line segmentation with Tesseract on the workspace.
        
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
        return self.recognizer.process()
