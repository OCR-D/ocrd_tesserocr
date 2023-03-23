import os
from test.base import TestCase, main, assets

from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegmentWord

class TestProcessorSegmentWordTesseract(TestCase):
    #METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/mets_one_file.xml')
    METS_HEROLD_SMALL = assets.url_of('kant_aufklaerung_1784-binarized/data/mets.xml')

    def test_run_modular(self):
        TesserocrSegmentRegion(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK"
        ).process()
        TesserocrSegmentLine(
            self.workspace,
            input_file_grp="OCR-D-SEG-BLOCK",
            output_file_grp="OCR-D-SEG-LINE"
        ).process()
        TesserocrSegmentWord(
            self.workspace,
            input_file_grp="OCR-D-SEG-LINE",
            output_file_grp="OCR-D-SEG-WORD"
        ).process()
        self.workspace.save_mets()

if __name__ == '__main__':
    main()
