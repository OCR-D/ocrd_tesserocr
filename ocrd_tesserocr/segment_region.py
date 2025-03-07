from __future__ import absolute_import

from typing import Optional

from ocrd_models import OcrdPage
from ocrd import OcrdPageResult

from .recognize import TesserocrRecognize

class TesserocrSegmentRegion(TesserocrRecognize):
    @property
    def executable(self) -> str:
        return 'ocrd-tesserocr-segment-region'

    def setup(self):
        # don't run super().setup(self) - helper will
        parameter = dict(self.parameter)
        # we already did validate and default-expand
        parameter['overwrite_segments'] = parameter['overwrite_regions']
        del parameter['overwrite_regions']
        parameter['segmentation_level'] = "region"
        parameter['textequiv_level'] = "region"
        parameter['block_polygons'] = parameter['crop_polygons']
        del parameter['crop_polygons']
        # this will validate and default-expand, then call helper's setup()
        self.helper = TesserocrRecognize(None, parameter=parameter)
        self.helper.logger = self.logger

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Performs region segmentation with Tesseract.

        Open and deserialize PAGE input file and its respective images,
        and remove any existing Region and ReadingOrder elements
        (unless ``overwrite_regions`` is False).

        Set up Tesseract to detect blocks, and add each one to the page
        as a region according to BlockType at the detected coordinates.
        If ``find_tables`` is True, try to detect table blocks and add them
        as (atomic) TableRegion.

        If ``crop_polygons`` is True, then query polygon outlines instead of
        bounding boxes from Tesseract for each region. (This is more precise,
        but due to some path representation errors does not always yield
        accurate/valid polygons.)

        If ``shrink_polygons``, then query Tesseract for all symbols/glyphs
        of each segment and calculate the convex hull for them.
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
