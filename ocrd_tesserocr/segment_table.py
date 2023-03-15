from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd_validators import ParameterValidator

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment-table'
BASE_TOOL = 'ocrd-tesserocr-recognize'

class TesserocrSegmentTable(TesserocrRecognize):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('ocrd_tool', OCRD_TOOL['tools'][TOOL])
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.parameter['overwrite_segments'] = self.parameter['overwrite_cells']
            del self.parameter['overwrite_cells']
            self.parameter['segmentation_level'] = "cell"
            self.parameter['textequiv_level'] = "cell"
            # add default params
            assert ParameterValidator(OCRD_TOOL['tools'][BASE_TOOL]).validate(self.parameter).is_valid
            self.logger = getLogger('processor.TesserocrSegmentTable')

TesserocrSegmentTable.process.__doc__ = """Performs table cell segmentation with Tesseract on the workspace.
        
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
