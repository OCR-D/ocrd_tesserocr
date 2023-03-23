import os
from test.base import TestCase, main, assets

from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegment

class TestProcessorSegmentLineTesseract(TestCase):
    METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/data/mets_one_file.xml')

    def test_run_modular(self):
        TesserocrSegmentRegion(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK"
        ).process()
        #  self.workspace.save_mets()
        TesserocrSegmentLine(
            self.workspace,
            input_file_grp="OCR-D-SEG-BLOCK",
            output_file_grp="OCR-D-SEG-LINE"
        ).process()
        self.workspace.save_mets()

    def test_run_allinone(self):
        TesserocrSegment(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG"
        ).process()
        self.workspace.save_mets()

if __name__ == '__main__':
    main(__file__)
