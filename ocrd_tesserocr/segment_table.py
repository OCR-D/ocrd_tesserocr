from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd import Processor

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment-table'

class TesserocrSegmentTable(Processor):

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
            recognize_kwargs['parameter']['overwrite_segments'] = self.parameter['overwrite_cells']
            del recognize_kwargs['parameter']['overwrite_regions']
            recognize_kwargs['parameter']['segmentation_level'] = "cell"
            recognize_kwargs['parameter']['textequiv_level'] = "cell"
            self.recognizer = TesserocrRecognize(self.workspace, **recognize_kwargs)
            self.recognizer.logger = getLogger('processor.TesserocrSegmentTable')

    def process(self):
        """Performs table cell segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the region level
        for table regions, and remove any existing TextRegion elements
        (unless ``overwrite_cells`` is False).
        
        Set up Tesseract to detect text blocks (as table cells).
        (This is not Tesseract's internal table structure recognition,
        but the general page segmentation in sparse mode.)
        Add each block to the table at the detected coordinates.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        return self.recognizer.process()
