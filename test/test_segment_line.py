from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegment
from ocrd_modelfactory import page_from_file
from ocrd_utils import MIMETYPE_PAGE

def test_run_modular(workspace_herold_small):
    TesserocrSegmentRegion(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG-BLOCK"
    ).process()
    #  workspace.save_mets()
    TesserocrSegmentLine(
        workspace_herold_small,
        input_file_grp="OCR-D-SEG-BLOCK",
        output_file_grp="OCR-D-SEG-LINE"
    ).process()
    out_files = list(workspace_herold_small.find_files(
        fileGrp="OCR-D-SEG-LINE", pageId="PHYS_0001", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_lines = out_pcgts.get_Page().get_AllTextLines()
    assert len(out_lines)
    workspace_herold_small.save_mets()

def test_run_allinone(workspace_herold_small):
    TesserocrSegment(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG"
    ).process()
    out_files = list(workspace_herold_small.find_files(
        fileGrp="OCR-D-SEG", pageId="PHYS_0001", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_lines = out_pcgts.get_Page().get_AllTextLines()
    assert len(out_lines)
    workspace_herold_small.save_mets()
