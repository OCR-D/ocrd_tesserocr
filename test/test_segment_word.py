import os
import shutil

from test.base import TestCase, main, assets

from ocrd.resolver import Resolver
from ocrd_tesserocr.segment_region import TesserocrSegmentRegion
from ocrd_tesserocr.segment_line import TesserocrSegmentLine
from ocrd_tesserocr.segment_word import TesserocrSegmentWord

WORKSPACE_DIR = '/tmp/pyocrd-test-segment-word-tesserocr'

class TestProcessorSegmentWordTesseract(TestCase):

    def setUp(self):
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)
        os.makedirs(WORKSPACE_DIR)

    def runTest(self):
        resolver = Resolver()
        #  workspace = resolver.workspace_from_url(assets.url_of('SBB0000F29300010000/mets_one_file.xml'), directory=WORKSPACE_DIR)
        workspace = resolver.workspace_from_url(assets.url_of('kant_aufklaerung_1784-binarized/mets.xml'), directory=WORKSPACE_DIR)
        TesserocrSegmentRegion(workspace, input_file_grp="OCR-D-IMG", output_file_grp="OCR-D-SEG-BLOCK").process()
        TesserocrSegmentLine(workspace, input_file_grp="OCR-D-SEG-BLOCK", output_file_grp="OCR-D-SEG-LINE").process()
        TesserocrSegmentWord(workspace, input_file_grp="OCR-D-SEG-LINE", output_file_grp="OCR-D-SEG-WORD").process()
        workspace.save_mets()

if __name__ == '__main__':
    main()
