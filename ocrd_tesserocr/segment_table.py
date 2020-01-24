from __future__ import absolute_import

import os.path
from tesserocr import (
    PyTessBaseAPI,
    PSM, RIL, PT
)

from ocrd_utils import (
    getLogger,
    concat_padded,
    coordinates_for_segment,
    polygon_from_x0y0x1y1,
    points_from_polygon,
    MIMETYPE_PAGE,
    membername
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    MetadataItemType,
    LabelsType, LabelType,
    CoordsType,
    TextRegionType,
    to_xml)
from ocrd_models.ocrd_page_generateds import (
    TableRegionType,
    TextTypeSimpleType,
    RegionRefType,
    RegionRefIndexedType,
    OrderedGroupType,
    OrderedGroupIndexedType,
    UnorderedGroupType,
    UnorderedGroupIndexedType,
    ReadingOrderType
)
from ocrd import Processor

from .config import TESSDATA_PREFIX, OCRD_TOOL
from .recognize import page_get_reading_order

TOOL = 'ocrd-tesserocr-segment-table'
LOG = getLogger('processor.TesserocrSegmentTable')

class TesserocrSegmentTable(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentTable, self).__init__(*args, **kwargs)

    def process(self):
        """Performs table cell segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the block level
        for table regions. If ``overwrite_regions`` is enabled and any
        layout annotation already exists inside, then remove it.
        
        Set up Tesseract to detect text blocks (as table cells).
        (This is not Tesseract's internal table structure recognition,
        but the general page segmentation.)
        Add each to the block at the detected coordinates.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        overwrite_regions = self.parameter['overwrite_regions']
        
        with PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            # disable table detection here, so we won't get
            # tables inside tables, but try to analyse them as
            # independent text/line blocks:
            tessapi.SetVariable("textord_tabfind_find_tables", "0")
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
                    LOG.info("setting user defined DPI %d from metadata", dpi)
                    tessapi.SetVariable('user_defined_dpi', str(dpi))

                #
                # prepare dict of reading order
                reading_order = dict()
                ro = page.get_ReadingOrder()
                if not ro:
                    LOG.warning("Page '%s' contains no ReadingOrder", page_id)
                    rogroup = None
                else:
                    rogroup = ro.get_OrderedGroup() or ro.get_UnorderedGroup()
                    page_get_reading_order(reading_order, rogroup)
                #
                # dive into regions
                regions = page.get_TableRegion()
                for region in regions:
                    # delete or warn of existing regions:
                    if region.get_TextRegion():
                        if overwrite_regions:
                            LOG.info('removing existing TextRegions in block "%s" of page "%s"', region.id, page_id)
                            for subregion in region.get_TextRegion():
                                if subregion.id in reading_order:
                                    regionref = reading_order[subregion.id]
                                    # could be any of the 6 types above:
                                    regionrefs = rogroup.__getattribute__(regionref.__class__.__name__.replace('Type', ''))
                                    # remove in-place
                                    regionrefs.remove(regionref)
                                    # TODO: adjust index to make contiguous again?
                            region.set_TextRegion([])
                        else:
                            LOG.warning('keeping existing TextRegions in block "%s" of page "%s"', region.id, page_id)
                    # get region image
                    region_image, region_coords = self.workspace.image_from_segment(
                        region, page_image, page_coords)
                    tessapi.SetImage(region_image)
                    LOG.info("Detecting table cells in region '%s'", region.id)
                    #
                    # detect the region segments:
                    tessapi.SetPageSegMode(PSM.AUTO) # treat table like page
                    layout = tessapi.AnalyseLayout()
                    roelem = reading_order.get(region.id)
                    if not roelem:
                        LOG.warning("Page '%s' table region '%s' is not referenced in reading order (%s)",
                                    page_id, region.id, "no target to add cells into")
                    elif isinstance(roelem, (OrderedGroupType, OrderedGroupIndexedType)):
                        LOG.warning("Page '%s' table region '%s' already has an ordered group (%s)",
                                    page_id, region.id, "cells will be appended")
                    elif isinstance(roelem, (UnorderedGroupType, UnorderedGroupIndexedType)):
                        LOG.warning("Page '%s' table region '%s' already has an unordered group (%s)",
                                    page_id, region.id, "cells will not be appended")
                        roelem = None
                    elif isinstance(roelem, RegionRefIndexedType):
                        # replace regionref by group with same index and ref
                        # (which can then take the cells as subregions)
                        roelem2 = OrderedGroupIndexedType(id=region.id + '_order',
                                                          index=roelem.index,
                                                          regionRef=roelem.regionRef)
                        roelem.parent_object_.add_OrderedGroupIndexed(roelem2)
                        roelem.parent_object_.get_RegionRefIndexed().remove(roelem)
                        roelem = roelem2
                    elif isinstance(roelem, RegionRefType):
                        # replace regionref by group with same ref
                        # (which can then take the cells as subregions)
                        roelem2 = OrderedGroupType(id=region.id + '_order',
                                                   regionRef=roelem.regionRef)
                        roelem.parent_object_.add_OrderedGroup(roelem2)
                        roelem.parent_object_.get_RegionRef().remove(roelem)
                        roelem = roelem2
                    self._process_region(layout, region, roelem, region_image, region_coords)
                    
                # Use input_file's basename for the new file -
                # this way the files retain the same basenames:
                file_id = input_file.ID.replace(self.input_file_grp, self.output_file_grp)
                if file_id == input_file.ID:
                    file_id = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    force=True,
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_region(self, it, region, rogroup, region_image, region_coords):
        # equivalent to GetComponentImages with raw_image=True,
        # (which would also give raw coordinates),
        # except we are also interested in the iterator's BlockType() here,
        index = 0
        if rogroup:
            for elem in (rogroup.get_RegionRefIndexed() +
                         rogroup.get_OrderedGroupIndexed() +
                         rogroup.get_UnorderedGroupIndexed()):
                if elem.index >= index:
                    index = elem.index + 1
        while it and not it.Empty(RIL.BLOCK):
            bbox = it.BoundingBox(RIL.BLOCK)
            polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, region_image, region_coords)
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            # if xywh['w'] < 30 or xywh['h'] < 30:
            #     LOG.info('Ignoring too small region: %s', points)
            #     it.Next(RIL.BLOCK)
            #     continue
            #
            # add the region reference in the reading order element
            # (but ignore non-text regions entirely)
            ID = region.id + "_%04d" % index
            subregion = TextRegionType(id=ID, Coords=coords,
                                       type=TextTypeSimpleType.PARAGRAPH)
            block_type = it.BlockType()
            if block_type == PT.FLOWING_TEXT:
                pass
            elif block_type == PT.HEADING_TEXT:
                subregion.set_type(TextTypeSimpleType.HEADING)
            elif block_type == PT.PULLOUT_TEXT:
                subregion.set_type(TextTypeSimpleType.FLOATING)
            elif block_type == PT.CAPTION_TEXT:
                subregion.set_type(TextTypeSimpleType.CAPTION)
            elif block_type == PT.VERTICAL_TEXT:
                subregion.set_orientation(90.0)
            else:
                it.Next(RIL.BLOCK)
                continue
            LOG.info("Detected cell '%s': %s (%s)", ID, points, membername(PT, block_type))
            region.add_TextRegion(subregion)
            if rogroup:
                rogroup.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
            #
            # iterator increment
            #
            index += 1
            it.Next(RIL.BLOCK)
