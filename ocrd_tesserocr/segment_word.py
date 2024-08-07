from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd_validators import ParameterValidator

from .recognize import TesserocrRecognize

class TesserocrSegmentWord(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-segment-word'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.parameter['overwrite_segments'] = self.parameter['overwrite_words']
            del self.parameter['overwrite_words']
            self.parameter['segmentation_level'] = "word"
            self.parameter['textequiv_level'] = "word"
            # add default params
            assert ParameterValidator(self.metadata['tools']['ocrd-tesserocr-recognize']).validate(self.parameter).is_valid

    def process_page_pcgts(self, pcgts, output_file_id=None, page_id=None):
        """Performs word segmentation with Tesseract on the workspace.
        
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
        return super().process_page_pcgts(pcgts, output_file_id=output_file_id, page_id=page_id)
