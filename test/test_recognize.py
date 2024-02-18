import os

from ocrd_models.constants import NAMESPACES
from ocrd_modelfactory import page_from_file
from ocrd_utils import MIMETYPE_PAGE
from ocrd_tesserocr import TesserocrDeskew
from ocrd_tesserocr import TesserocrSegmentWord
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrRecognize
from ocrd_tesserocr import TesserocrFontShape

def test_run_modular(workspace_kant_binarized):
    TesserocrSegmentRegion(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG-BLOCK"
    ).process()
    TesserocrSegmentLine(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-BLOCK",
        output_file_grp="OCR-D-SEG-LINE"
    ).process()
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-LINE",
        output_file_grp="OCR-D-OCR-TESS",
        parameter={'textequiv_level': 'line', 'model': 'Fraktur'}
    ).process()
    TesserocrSegmentWord(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-LINE",
        output_file_grp="OCR-D-SEG-WORD"
    ).process()
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-WORD",
        output_file_grp="OCR-D-OCR-TESS-W2C",
        parameter={'segmentation_level': 'glyph', 'textequiv_level': 'glyph', 'model': 'Fraktur'}
    ).process()
    workspace_kant_binarized.save_mets()
    assert os.path.isdir(os.path.join(workspace_kant_binarized.directory, 'OCR-D-OCR-TESS-W2C'))
    results = workspace_kant_binarized.find_files(file_grp='OCR-D-OCR-TESS-W2C', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    _, result0, _, _ = page_from_file(result0, with_tree=True)
    text0 = result0.xpath('//page:Glyph/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0

def test_run_modular_full(workspace_kant_binarized):
    TesserocrDeskew(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-DESK",
        parameter={"operation_level": "page"}
    ).process()
    TesserocrSegmentRegion(
        workspace_kant_binarized,
        input_file_grp="OCR-D-DESK",
        output_file_grp="OCR-D-SEG-BLOCK"
    ).process()
    TesserocrDeskew(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-BLOCK",
        output_file_grp="OCR-D-DESK-BLOCK",
        parameter={"operation_level": "region"}
    ).process()
    TesserocrSegmentLine(
        workspace_kant_binarized,
        input_file_grp="OCR-D-DESK-BLOCK",
        output_file_grp="OCR-D-SEG-LINE"
    ).process()
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-LINE",
        output_file_grp="OCR-D-OCR-TESS",
        parameter={'textequiv_level': 'word', 'raw_lines': True, 'xpath_model': {'starts-with(@script,"Latn")': 'deu+eng', 'starts-with(@script,"Latf")': 'Fraktur'}, 'model': 'Fraktur+deu+eng'}
    ).process()
    TesserocrFontShape(
        workspace_kant_binarized,
        input_file_grp="OCR-D-OCR-TESS",
        output_file_grp="OCR-D-OCR-STYLE"
    ).process()
    workspace_kant_binarized.save_mets()
    assert os.path.isdir(os.path.join(workspace_kant_binarized.directory, 'OCR-D-OCR-STYLE'))
    results = workspace_kant_binarized.find_files(file_grp='OCR-D-OCR-STYLE', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    _, result0, _, _ = page_from_file(result0, with_tree=True)
    text0 = result0.xpath('//page:Word/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0
    style0 = result0.xpath('//page:Word/page:TextStyle', namespaces=NAMESPACES)
    assert len(style0) > 0

def test_run_allinone(workspace_kant_binarized):
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-OCR-TESS-W2C",
        parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'model': 'Fraktur'}
    ).process()
    workspace_kant_binarized.save_mets()
    assert os.path.isdir(os.path.join(workspace_kant_binarized.directory, 'OCR-D-OCR-TESS-W2C'))
    results = workspace_kant_binarized.find_files(file_grp='OCR-D-OCR-TESS-W2C', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    _, result0, _, _ = page_from_file(result0, with_tree=True)
    text0 = result0.xpath('//page:Glyph/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0

def test_run_allinone_shrink(workspace_kant_binarized):
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-OCR-TESS-W2C",
        parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'shrink_polygons': True, 'model': 'Fraktur'}
    ).process()
    workspace_kant_binarized.save_mets()

def test_run_allinone_sparse(workspace_kant_binarized):
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-OCR-TESS-W2C",
        parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'sparse_text': True, 'model': 'Fraktur'}
    ).process()
    workspace_kant_binarized.save_mets()

def test_run_allineone_multimodel(workspace_kant_binarized):
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-OCR-TESS-W2C",
        parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'model': 'Fraktur+eng+deu'}
    ).process()
    workspace_kant_binarized.save_mets()

# @skip
def test_run_allinone_automodel(workspace_kant_binarized):
    TesserocrRecognize(
        workspace_kant_binarized,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-OCR-TESS-W2C",
        parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'auto_model': True, 'model': 'Fraktur+eng+deu'}
    ).process()
    workspace_kant_binarized.save_mets()
