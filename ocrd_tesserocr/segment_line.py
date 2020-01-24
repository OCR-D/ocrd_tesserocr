from __future__ import absolute_import

import itertools
import os.path
from shapely.geometry import Polygon, LinearRing
from tesserocr import PyTessBaseAPI, RIL, PSM

from ocrd import Processor
from ocrd_utils import (
    getLogger, concat_padded,
    polygon_from_xywh,
    points_from_polygon,
    coordinates_for_segment,
    coordinates_of_segment,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,
    LabelType, LabelsType,
    MetadataItemType,
    TextLineType,
    to_xml
)

from .config import TESSDATA_PREFIX, OCRD_TOOL

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
        overwrite_lines = self.parameter['overwrite_lines']
        
        with PyTessBaseAPI(
                psm=PSM.SINGLE_BLOCK,
                path=TESSDATA_PREFIX
        ) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                page = pcgts.get_Page()
                
                # add metadata about this operation and its runtime parameters:
                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=self.ocrd_tool['steps'][0],
                                     value=TOOL,
                                     Labels=[LabelsType(
                                         externalModel="ocrd-tool",
                                         externalId="parameters",
                                         Label=[LabelType(type_=name,
                                                          value=self.parameter[name])
                                                for name in self.parameter.keys()])]))
                
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
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
                    region_polygon = coordinates_of_segment(region, region_image, region_coords)
                    region_poly = Polygon(region_polygon)
                    tessapi.SetImage(region_image)
                    for line_no, component in enumerate(tessapi.GetComponentImages(RIL.TEXTLINE, True, raw_image=True)):
                        line_id = '%s_line%04d' % (region.id, line_no)
                        line_polygon = polygon_from_xywh(component[1])
                        line_poly = Polygon(line_polygon)
                        if not line_poly.within(region_poly):
                            # this could happen due to rotation
                            line_poly = line_poly.intersection(region_poly).convex_hull
                            line_polygon = line_poly.exterior.coords
                        line_polygon = coordinates_for_segment(line_polygon, region_image, region_coords)
                        line_points = points_from_polygon(line_polygon)
                        region.add_TextLine(TextLineType(
                            id=line_id, Coords=CoordsType(line_points)))
                
                # Use input_file's basename for the new file -
                # this way the files retain the same basenames:
                file_id = input_file.ID.replace(self.input_file_grp, self.output_file_grp)
                if file_id == input_file.ID:
                    file_id = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))
