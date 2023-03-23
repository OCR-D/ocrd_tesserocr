import os
from test.base import TestCase, main, assets, skip

from ocrd_tesserocr import TesserocrSegmentRegion

class TestTesserocrSegmentRegionTesseract(TestCase):
    METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/data/mets_one_file.xml')

    def test_run(self):
        TesserocrSegmentRegion(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK"
        ).process()
        self.workspace.save_mets()

    def test_run_shrink(self):
        TesserocrSegmentRegion(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK",
            parameter={'shrink_polygons': True}
        ).process()
        self.workspace.save_mets()

    def test_run_sparse(self):
        TesserocrSegmentRegion(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK",
            parameter={'sparse_text': True}
        ).process()
        self.workspace.save_mets()

    def test_run_staves(self):
        TesserocrSegmentRegion(
            self.workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK",
            parameter={'find_staves': True, 'find_tables': False}
        ).process()
        self.workspace.save_mets()

if __name__ == '__main__':
    main(__file__)
