from __future__ import absolute_import

from typing import Optional

from ocrd_models import OcrdPage
from ocrd import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegmentLine(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment-line'

    def setup(self):
        # don't run super().setup(self) - helper will
        parameter = dict(self.parameter)
        # we already did validate and default-expand
        parameter['overwrite_segments'] = parameter['overwrite_lines']
        del parameter['overwrite_lines']
        parameter['segmentation_level'] = "line"
        parameter['textequiv_level'] = "line"
        # this will validate and default-expand, then call helper's setup()
        self.helper = TesserocrRecognize(None, parameter=parameter)
        self.helper.logger = self.logger

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs (text) line segmentation with Tesseract.

        Open and deserialize PAGE input file and its respective images,
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
        # delegate implementation to helper tool
        self.helper.workspace = self.workspace
        self.helper.page_id = self.page_id
        self.helper.input_file_grp = self.input_file_grp
        self.helper.output_file_grp = self.output_file_grp
        return self.helper.process_page_pcgts(*input_pcgts, page_id=page_id)
