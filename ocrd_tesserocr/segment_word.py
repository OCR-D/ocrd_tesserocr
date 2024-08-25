from __future__ import absolute_import

from typing import Optional

from ocrd_models import OcrdPage
from ocrd import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegmentWord(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment-word'

    def setup(self):
        # don't run super().setup(self) - helper will
        parameter = dict(self.parameter)
        # we already did validate and default-expand
        parameter['overwrite_segments'] = parameter['overwrite_words']
        del parameter['overwrite_words']
        parameter['segmentation_level'] = "word"
        parameter['textequiv_level'] = "word"
        # this will validate and default-expand, then call helper's setup()
        self.helper = TesserocrRecognize(None, parameter=parameter)
        self.helper.logger = self.logger

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs word segmentation with Tesseract.

        Open and deserialize PAGE input file and its respective images,
        then iterate over the element hierarchy down to the textline level,
        and remove any existing Word elements.

        Set up Tesseract to detect words, and add each one to the line
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
