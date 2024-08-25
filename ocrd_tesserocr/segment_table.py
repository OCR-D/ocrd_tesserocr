from __future__ import absolute_import

from typing import Optional

from ocrd_models import OcrdPage
from ocrd import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegmentTable(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment-table'

    def setup(self):
        # don't run super().setup(self) - helper will
        parameter = dict(self.parameter)
        # we already did validate and default-expand
        parameter['overwrite_segments'] = parameter['overwrite_cells']
        del parameter['overwrite_cells']
        parameter['segmentation_level'] = "cell"
        parameter['textequiv_level'] = "cell"
        # this will validate and default-expand, then call helper's setup()
        self.helper = TesserocrRecognize(None, parameter=parameter)
        self.helper.logger = self.logger

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs table cell segmentation with Tesseract.

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
        # delegate implementation to helper tool
        self.helper.workspace = self.workspace
        self.helper.page_id = self.page_id
        self.helper.input_file_grp = self.input_file_grp
        self.helper.output_file_grp = self.output_file_grp
        return self.helper.process_page_pcgts(*input_pcgts, page_id=page_id)

