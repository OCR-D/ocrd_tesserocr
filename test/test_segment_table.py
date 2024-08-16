from ocrd import run_processor
from ocrd_tesserocr import TesserocrSegment, TesserocrSegmentRegion, TesserocrSegmentTable
from ocrd_modelfactory import page_from_file
from ocrd_utils import MIMETYPE_PAGE

def test_run_modular(workspace_gutachten):
    run_processor(TesserocrSegmentRegion,
                  workspace=workspace_gutachten,
                  input_file_grp="IMG",
                  output_file_grp="OCR-D-SEG-BLOCK",
                  parameter={'find_tables': True, 'overwrite_regions': True})
    run_processor(TesserocrSegmentTable,
                  workspace=workspace_gutachten,
                  input_file_grp="OCR-D-SEG-BLOCK",
                  output_file_grp="OCR-D-SEG-CELL")
    out_files = list(workspace_gutachten.find_files(
        fileGrp="OCR-D-SEG-CELL", pageId="PHYS_1", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_tables = out_pcgts.get_Page().get_AllRegions(classes=['Table'])
    assert len(out_tables)
    workspace_gutachten.save_mets()

def test_run_allinone(workspace_gutachten):
    run_processor(TesserocrSegment,
                  workspace=workspace_gutachten,
                  input_file_grp="IMG",
                  output_file_grp="OCR-D-SEG",
                  parameter={'find_tables': True} # , 'textequiv_level': 'cell'
                  )
    run_processor(TesserocrSegmentTable,
                  workspace=workspace_gutachten,
                  input_file_grp="OCR-D-SEG",
                output_file_grp="OCR-D-SEG-CELL",
                  parameter={'overwrite_cells': True})
    out_files = list(workspace_gutachten.find_files(
        fileGrp="OCR-D-SEG-CELL", pageId="PHYS_1", mimetype=MIMETYPE_PAGE))
    assert len(out_files)
    out_pcgts = page_from_file(out_files[0])
    assert out_pcgts is not None
    out_tables = out_pcgts.get_Page().get_AllRegions(classes=['Table'])
    assert len(out_tables)
    workspace_gutachten.save_mets()

