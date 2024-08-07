from ocrd import run_processor
from ocrd_tesserocr import TesserocrSegmentRegion
from ocrd_modelfactory import page_from_file
from ocrd_utils import MIMETYPE_PAGE

def test_run(workspace_herold_small):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_herold_small,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-SEG-BLOCK")
    out_files = list(workspace_herold_small.find_files(
        fileGrp="OCR-D-SEG-BLOCK", pageId="PHYS_0001", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_blocks = out_pcgts.get_Page().get_AllRegions(classes=['Text'])
    assert len(out_blocks)
    workspace_herold_small.save_mets()

def test_run_shrink(workspace_herold_small):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_herold_small,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-SEG-BLOCK",
                  parameter={'shrink_polygons': True})
    out_files = list(workspace_herold_small.find_files(
        fileGrp="OCR-D-SEG-BLOCK", pageId="PHYS_0001", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_blocks = out_pcgts.get_Page().get_AllRegions(classes=['Text'])
    assert len(out_blocks)
    workspace_herold_small.save_mets()

def test_run_sparse(workspace_herold_small):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_herold_small,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-SEG-BLOCK",
                  parameter={'sparse_text': True})
    out_files = list(workspace_herold_small.find_files(
        fileGrp="OCR-D-SEG-BLOCK", pageId="PHYS_0001", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_blocks = out_pcgts.get_Page().get_AllRegions(classes=['Text'])
    assert len(out_blocks)
    workspace_herold_small.save_mets()

def test_run_staves(workspace_herold_small):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_herold_small,
                  input_file_grp="OCR-D-IMG",
                  output_file_grp="OCR-D-SEG-BLOCK",
                  parameter={'find_staves': True, 'find_tables': False})
    out_files = list(workspace_herold_small.find_files(
        fileGrp="OCR-D-SEG-BLOCK", pageId="PHYS_0001", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_blocks = out_pcgts.get_Page().get_AllRegions(classes=['Text'])
    assert len(out_blocks)
    workspace_herold_small.save_mets()
