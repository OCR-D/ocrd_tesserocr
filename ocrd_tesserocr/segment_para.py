from __future__ import absolute_import

from typing import Optional

from ocrd_models import OcrdPage
from ocrd import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegmentPara(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment-para'

    def setup(self):
        # don't run super().setup(self) - helper will
        parameter = dict(self.parameter)
        parameter['segmentation_level'] = "cell"
        parameter['textequiv_level'] = "cell"
        parameter['paragraphs'] = "recursive"
        # this will validate and default-expand, then call helper's setup()
        self.helper = TesserocrRecognize(None, parameter=parameter)
        self.helper.logger = self.logger

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs paragraph segmentation with Tesseract.

        Open and deserialize PAGE input file and its respective images,
        then iterate over the element hierarchy down to the region level
        for text regions.

        Set up Tesseract to detect paragraphs.
        Add each paragraph as a recursive TextRegion at the detected coordinates.
        If TextLines exist at the top region level, try to move them down
        to the new paragraph regions.

        Produce a new output file by serialising the resulting hierarchy.
        """
        # delegate implementation to helper tool
        self.helper.workspace = self.workspace
        self.helper.page_id = self.page_id
        self.helper.input_file_grp = self.input_file_grp
        self.helper.output_file_grp = self.output_file_grp
        return self.helper.process_page_pcgts(*input_pcgts, page_id=page_id)

