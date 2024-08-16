from __future__ import absolute_import

from typing import Optional

from ocrd_utils import getLogger
from ocrd_validators import ParameterValidator
from ocrd_models import OcrdPage
from ocrd.processor import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegmentTable(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment-table'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.parameter['overwrite_segments'] = self.parameter['overwrite_cells']
            del self.parameter['overwrite_cells']
            self.parameter['segmentation_level'] = "cell"
            self.parameter['textequiv_level'] = "cell"
            # add default params
            assert ParameterValidator(self.metadata['tools']['ocrd-tesserocr-recognize']).validate(self.parameter).is_valid

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs table cell segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input file and its respective images,
        then iterate over the element hierarchy down to the region level
        for table regions, and remove any existing TextRegion elements
        (unless ``overwrite_cells`` is False).
        
        Set up Tesseract to detect text blocks (as table cells).
        (This is not Tesseract's internal table structure recognition,
        but the general page segmentation in sparse mode.)
        Add each block to the table at the detected coordinates.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        return super().process_page_pcgts(*input_pcgts, page_id=page_id)
