from __future__ import absolute_import

import itertools
import os.path
from tesserocr import PyTessBaseAPI, RIL, PSM

from ocrd import Processor
from ocrd_utils import (
    getLogger,
    make_file_id,
    assert_file_grp_cardinality,
    polygon_from_xywh,
    points_from_polygon,
    coordinates_for_segment,
    coordinates_of_segment,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,
    TextLineType,
    to_xml
)

from .config import TESSDATA_PREFIX, OCRD_TOOL
from .segment_region import polygon_for_parent

TOOL = 'ocrd-tesserocr-segment-line'
LOG = getLogger('processor.TesserocrSegmentLine')

class TesserocrSegmentLine(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentLine, self).__init__(*args, **kwargs)


    def process(self):
        """Performs (text) line segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the (text) region level,
        and remove any existing TextLine elements (unless ``overwrite_lines``
        is False).
        
        Set up Tesseract to detect lines, and add each one to the region
        at the detected coordinates.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        overwrite_lines = self.parameter['overwrite_lines']
        
        with PyTessBaseAPI(
                psm=PSM.SINGLE_BLOCK,
                path=TESSDATA_PREFIX
        ) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if self.parameter['dpi'] > 0:
                    dpi = self.parameter['dpi']
                    LOG.info("Page '%s' images will use %d DPI from parameter override", page_id, dpi)
                elif page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
                    LOG.info("Page '%s' images will use %d DPI from image meta-data", page_id, dpi)
                else:
                    dpi = 0
                    LOG.info("Page '%s' images will use DPI estimated from segmentation", page_id)
                if dpi:
                    tessapi.SetVariable('user_defined_dpi', str(dpi))
                
                for region in itertools.chain.from_iterable(
                        [page.get_TextRegion()] +
                        [subregion.get_TextRegion() for subregion in page.get_TableRegion()]):
                    if region.get_TextLine():
                        if overwrite_lines:
                            LOG.info('removing existing TextLines in region "%s"', region.id)
                            region.set_TextLine([])
                        else:
                            LOG.warning('keeping existing TextLines in region "%s"', region.id)
                    LOG.debug("Detecting lines in region '%s'", region.id)
                    region_image, region_coords = self.workspace.image_from_segment(
                        region, page_image, page_coords)
                    tessapi.SetImage(region_image)
                    for line_no, component in enumerate(tessapi.GetComponentImages(RIL.TEXTLINE, True, raw_image=True)):
                        line_id = '%s_line%04d' % (region.id, line_no)
                        line_polygon = polygon_from_xywh(component[1])
                        line_polygon = coordinates_for_segment(line_polygon, region_image, region_coords)
                        line_polygon2 = polygon_for_parent(line_polygon, region)
                        if line_polygon2 is not None:
                            line_polygon = line_polygon2
                        line_points = points_from_polygon(line_polygon)
                        if line_polygon2 is None:
                            # could happen due to rotation
                            LOG.info('Ignoring extant line: %s', line_points)
                            continue
                        region.add_TextLine(TextLineType(
                            id=line_id, Coords=CoordsType(line_points)))
                
                file_id = make_file_id(input_file, self.output_file_grp)
                pcgts.set_pcGtsId(file_id)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))
