import os
import shutil

from test.base import TestCase, main, assets, skip

from ocrd.resolver import Resolver
from ocrd_tesserocr.segment_word import TesserocrSegmentWord
from ocrd_tesserocr.segment_line import TesserocrSegmentLine
from ocrd_tesserocr.segment_region import TesserocrSegmentRegion
from ocrd_tesserocr.recognize import TesserocrRecognize

WORKSPACE_DIR = '/tmp/pyocrd-test-recognizer'

class TestTesserocrRecognize(TestCase):

    def setUp(self):
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)
        os.makedirs(WORKSPACE_DIR)

    #skip("Takes too long")
    def runTest(self):
        resolver = Resolver()
        #  workspace = resolver.workspace_from_url(assets.url_of('SBB0000F29300010000/mets_one_file.xml'), directory=WORKSPACE_DIR)
        workspace = resolver.workspace_from_url(assets.url_of('kant_aufklaerung_1784-page-block-line-word/mets.xml'), directory=WORKSPACE_DIR)
        TesserocrSegmentRegion(
            workspace,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-SEG-BLOCK"
        ).process()
        workspace.save_mets()
        TesserocrSegmentLine(
            workspace,
            input_file_grp="OCR-D-SEG-BLOCK",
            output_file_grp="OCR-D-SEG-LINE"
        ).process()
        workspace.save_mets()
        TesserocrRecognize(
            workspace,
            input_file_grp="OCR-D-SEG-LINE",
            output_file_grp="OCR-D-OCR-TESS",
            parameter={'textequiv_level': 'line'} # add dep tesseract-ocr-script-frak: , 'model': 'Fraktur'
        ).process()
        workspace.save_mets()
        TesserocrSegmentWord(
            workspace,
            input_file_grp="OCR-D-SEG-LINE",
            output_file_grp="OCR-D-SEG-WORD"
        ).process()
        workspace.save_mets()
        TesserocrRecognize(
            workspace,
            input_file_grp="OCR-D-SEG-WORD",
            output_file_grp="OCR-D-OCR-TESS-W2C",
            parameter={'textequiv_level': 'glyph'} # add dep tesseract-ocr-script-frak: , 'model': 'Fraktur'}
        ).process()
        workspace.save_mets()

if __name__ == '__main__':
    main()
