from __future__ import absolute_import

from typing import Optional

from ocrd_models import OcrdPage
from ocrd import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegment(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment'

    def setup(self):
        # don't run super().setup(self) - helper will
        parameter = dict(self.parameter)
        # we already did validate and default-expand
        parameter['overwrite_segments'] = True
        parameter['segmentation_level'] = "region"
        parameter['textequiv_level'] = "none"
        # this will validate and default-expand, then call helper's setup()
        self.helper = TesserocrRecognize(None, parameter=parameter)
        self.helper.logger = self.logger

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs region and line segmentation with Tesseract.

        Open and deserialize PAGE input file and its respective images,
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
        # delegate implementation to helper tool
        self.helper.workspace = self.workspace
        self.helper.page_id = self.page_id
        self.helper.input_file_grp = self.input_file_grp
        self.helper.output_file_grp = self.output_file_grp
        return self.helper.process_page_pcgts(*input_pcgts, page_id=page_id)

