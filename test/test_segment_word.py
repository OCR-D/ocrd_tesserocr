from ocrd import run_processor
from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegmentWord
from ocrd_modelfactory import page_from_file
from ocrd_utils import MIMETYPE_PAGE

def test_run_modular(workspace_kant_binarized):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-SEG-BLOCK")
    run_processor(TesserocrSegmentLine,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-BLOCK",
                  output_file_grp="OCR-D-SEG-LINE")
    run_processor(TesserocrSegmentWord,
                  workspace=workspace_kant_binarized,
                  input_file_grp="OCR-D-SEG-LINE",
                  output_file_grp="OCR-D-SEG-WORD")
    out_files = list(workspace_kant_binarized.find_files(
        fileGrp="OCR-D-SEG-WORD", pageId="P_0017", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_lines = out_pcgts.get_Page().get_AllTextLines()
    assert len(out_lines)
    assert all(len(line.get_Word()) for line in out_lines)
    workspace_kant_binarized.save_mets()
