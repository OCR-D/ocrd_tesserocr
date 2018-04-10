import os
import shutil

from test.base import TestCase, main, assets, skip

from ocrd.resolver import Resolver
from ocrd_tesserocr.segment_line import TesserocrSegmentLine
from ocrd_tesserocr.segment_region import TesserocrSegmentRegion
#  from ocrd_tesserocr.recognize import TesserocrRecognize

METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/mets_one_file.xml')

WORKSPACE_DIR = '/tmp/pyocrd-test-recognizer'

class TestTesserocrRecognize(TestCase):

    def setUp(self):
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)
        os.makedirs(WORKSPACE_DIR)

    skip("Takes too long")
    def runTest(self):
        resolver = Resolver(cache_enabled=True)
        workspace = resolver.workspace_from_url(METS_HEROLD_SMALL, directory=WORKSPACE_DIR)
        TesserocrSegmentRegion(workspace, inputGrp="INPUT", output_filegrp="OCR-D-SEG-BLOCK").process()
        workspace.save_mets()
        TesserocrSegmentLine(workspace, inputGrp="OCR-D-SEG-BLOCK", output_filegrp="OCR-D-SEG-LINE").process()
        workspace.save_mets()
        #  TODO takes too long
        #  TesserocrRecognize(workspace, inputGrp="OCR-D-SEG-LINE", output_filegrp="OCR-D-OCR-TESS").process()
        workspace.save_mets()

if __name__ == '__main__':
    main()
