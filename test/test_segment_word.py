from ocrd_tesserocr import (TesserocrSegmentLine, TesserocrSegmentRegion,
                            TesserocrSegmentWord)


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
    TesserocrSegmentWord(
        workspace_kant_binarized,
        input_file_grp="OCR-D-SEG-LINE",
        output_file_grp="OCR-D-SEG-WORD"
    ).process()
    workspace_kant_binarized.save_mets()
