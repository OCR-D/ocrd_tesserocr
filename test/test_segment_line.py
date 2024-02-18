from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_tesserocr import TesserocrSegmentLine
from ocrd_tesserocr import TesserocrSegment

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
    workspace_herold_small.save_mets()

def test_run_allinone(workspace_herold_small):
    TesserocrSegment(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG"
    ).process()
    workspace_herold_small.save_mets()
