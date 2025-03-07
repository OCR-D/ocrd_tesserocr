import os

from ocrd import run_processor
from ocrd_models.constants import NAMESPACES
from ocrd_modelfactory import page_from_file
from ocrd_utils import MIMETYPE_PAGE, config
from ocrd_tesserocr import TesserocrDeskew
from ocrd_tesserocr import TesserocrSegmentWord
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrRecognize
from ocrd_tesserocr import TesserocrFontShape

def test_run_modular(workspace_kant_binarized):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-SEG-BLOCK")
    run_processor(TesserocrSegmentLine,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-BLOCK",
                  output_file_grp="OCR-D-SEG-LINE")
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-LINE",
                  output_file_grp="OCR-D-OCR-TESS",
                  parameter={'textequiv_level': 'line', 'model': 'Fraktur'})
    run_processor(TesserocrSegmentWord,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-LINE",
                  output_file_grp="OCR-D-SEG-WORD")
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-WORD",
                  output_file_grp="OCR-D-OCR-TESS-W2C",
                  parameter={'segmentation_level': 'glyph', 'textequiv_level': 'glyph',
                             'model': 'Fraktur'})
    ws = workspace_kant_binarized
    ws.save_mets()
    assert os.path.isdir(os.path.join(ws.directory, 'OCR-D-OCR-TESS-W2C'))
    results = ws.find_files(file_grp='OCR-D-OCR-TESS-W2C', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    result0 = page_from_file(result0)
    text0 = result0.etree.xpath('//page:Glyph/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0

def test_run_modular_full(workspace_kant_binarized):
    run_processor(TesserocrDeskew,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-DESK",
                  parameter={"operation_level": "page"})
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-DESK",
                  output_file_grp="OCR-D-SEG-BLOCK")
    run_processor(TesserocrDeskew,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-BLOCK",
                  output_file_grp="OCR-D-DESK-BLOCK",
                  parameter={"operation_level": "region"})
    run_processor(TesserocrSegmentLine,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-DESK-BLOCK",
                  output_file_grp="OCR-D-SEG-LINE")
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-LINE",
                  output_file_grp="OCR-D-OCR-TESS",
                  parameter={'textequiv_level': 'word', 'raw_lines': True,
                             'xpath_model': {'starts-with(@script,"Latn")': 'deu+eng',
                                             'starts-with(@script,"Latf")': 'Fraktur'},
                             'model': 'Fraktur+deu+eng'})
    run_processor(TesserocrFontShape,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-OCR-TESS",
                  output_file_grp="OCR-D-OCR-STYLE")
    workspace_kant_binarized.save_mets()
    assert os.path.isdir(os.path.join(workspace_kant_binarized.directory, 'OCR-D-OCR-STYLE'))
    results = workspace_kant_binarized.find_files(file_grp='OCR-D-OCR-STYLE', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    result0 = page_from_file(result0)
    text0 = result0.etree.xpath('//page:Word/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0
    style0 = result0.etree.xpath('//page:Word/page:TextStyle', namespaces=NAMESPACES)
    assert len(style0) > 0

def test_run_allinone(workspace_kant_binarized):
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-OCR-TESS-W2C",
                  parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'model': 'Fraktur'})
    workspace_kant_binarized.save_mets()
    assert os.path.isdir(os.path.join(workspace_kant_binarized.directory, 'OCR-D-OCR-TESS-W2C'))
    results = workspace_kant_binarized.find_files(file_grp='OCR-D-OCR-TESS-W2C', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    result0 = page_from_file(result0)
    text0 = result0.etree.xpath('//page:Glyph/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0

def test_run_allinone_shrink(workspace_kant_binarized):
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-OCR-TESS-W2C",
                  parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'shrink_polygons': True,
                             'model': 'Fraktur'})
    workspace_kant_binarized.save_mets()

def test_run_allinone_sparse(workspace_kant_binarized):
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-OCR-TESS-W2C",
                  parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'sparse_text': True,
                             'model': 'Fraktur'})
    workspace_kant_binarized.save_mets()

def test_run_allineone_multimodel(workspace_kant_binarized):
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-OCR-TESS-W2C",
                  parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'model': 'Fraktur+eng+deu'})
    workspace_kant_binarized.save_mets()

# @skip
def test_run_allinone_automodel(workspace_kant_binarized):
    run_processor(TesserocrRecognize,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-OCR-TESS-W2C",
                  parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'auto_model': True,
                             'model': 'Fraktur+eng+deu'})
    workspace_kant_binarized.save_mets()

def test_run_allinone_cached(workspace_kant_binarized):
    processor_instance = None
    for run in range(5):
        if run >= 4:
            # default is SKIP
            config.OCRD_EXISTING_OUTPUT = "OVERWRITE"
        processor = run_processor(
            TesserocrRecognize,
            workspace=workspace_kant_binarized,
            input_file_grp="OCR-D-IMG",
            output_file_grp="OCR-D-OCR-TESS-W2C",
            parameter={'segmentation_level': 'region', 'textequiv_level': 'glyph', 'model': 'Fraktur'},
            instance_caching=True
        )
        if processor_instance is None:
            processor_instance = processor
        else:
            assert processor is processor_instance
    workspace_kant_binarized.save_mets()
    assert os.path.isdir(os.path.join(workspace_kant_binarized.directory, 'OCR-D-OCR-TESS-W2C'))
    results = workspace_kant_binarized.find_files(file_grp='OCR-D-OCR-TESS-W2C', mimetype=MIMETYPE_PAGE)
    result0 = next(results, False)
    assert result0
    result0 = page_from_file(result0)
    text0 = result0.etree.xpath('//page:Glyph/page:TextEquiv/page:Unicode', namespaces=NAMESPACES)
    assert len(text0) > 0
