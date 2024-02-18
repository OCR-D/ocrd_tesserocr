from ocrd_tesserocr import TesserocrSegmentRegion

def test_run(workspace_herold_small):
    TesserocrSegmentRegion(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG-BLOCK"
    ).process()
    workspace_herold_small.save_mets()

def test_run_shrink(workspace_herold_small):
    TesserocrSegmentRegion(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG-BLOCK",
        parameter={'shrink_polygons': True}
    ).process()
    workspace_herold_small.save_mets()

def test_run_sparse(workspace_herold_small):
    TesserocrSegmentRegion(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG-BLOCK",
        parameter={'sparse_text': True}
    ).process()
    workspace_herold_small.save_mets()

def test_run_staves(workspace_herold_small):
    TesserocrSegmentRegion(
        workspace_herold_small,
        input_file_grp="OCR-D-IMG",
        output_file_grp="OCR-D-SEG-BLOCK",
        parameter={'find_staves': True, 'find_tables': False}
    ).process()
    workspace_herold_small.save_mets()
