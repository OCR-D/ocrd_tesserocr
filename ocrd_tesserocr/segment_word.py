from __future__ import absolute_import

from ocrd_utils import getLogger
from ocrd import Processor

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-segment-word'

class TesserocrSegmentWord(Processor):

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
            recognize_kwargs['parameter']['overwrite_segments'] = self.parameter['overwrite_words']
            del recognize_kwargs['parameter']['overwrite_words']
            recognize_kwargs['parameter']['segmentation_level'] = "word"
            recognize_kwargs['parameter']['textequiv_level'] = "none"
            self.recognizer = TesserocrRecognize(self.workspace, **recognize_kwargs)
            self.recognizer.logger = getLogger('processor.TesserocrSegmentWord')

    def process(self):
        """Performs word segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the textline level,
        and remove any existing Word elements.
        
        Set up Tesseract to detect words, and add each one to the line
        at the detected coordinates.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        return self.recognizer.process()
