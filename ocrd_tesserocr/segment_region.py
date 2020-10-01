from __future__ import absolute_import

import os.path
import numpy as np
from shapely.geometry import Polygon, asPolygon
from shapely.ops import unary_union
from tesserocr import (
    PyTessBaseAPI,
    PSM, RIL, PT
)

from ocrd_utils import (
    getLogger,
    make_file_id,
    assert_file_grp_cardinality,
    coordinates_for_segment,
    polygon_from_points,
    polygon_from_x0y0x1y1,
    points_from_polygon,
    MIMETYPE_PAGE,
    membername
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,
    PageType,
    OrderedGroupType,
    ReadingOrderType,
    RegionRefIndexedType,
    TextRegionType,
    ImageRegionType,
    MathsRegionType,
    SeparatorRegionType,
    NoiseRegionType,
    to_xml)
from ocrd_models.ocrd_page_generateds import (
    TableRegionType,
    TextLineType,
    TextTypeSimpleType
)
from ocrd import Processor

from .config import TESSDATA_PREFIX, OCRD_TOOL

TOOL = 'ocrd-tesserocr-segment-region'

class TesserocrSegmentRegion(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentRegion, self).__init__(*args, **kwargs)

    def process(self):
        """Performs region segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        and remove any existing Region and ReadingOrder elements
        (unless ``overwrite_regions`` is False).
        
        Set up Tesseract to detect blocks, and add each one to the page
        as a region according to BlockType at the detected coordinates.
        If ``find_tables`` is True, try to detect table blocks and add them
        as (atomic) TableRegion.
        
        If ``crop_polygons`` is True, then query polygon outlines instead of
        bounding boxes from Tesseract for each region. (This is more precise,
        but due to some path representation errors does not always yield
        accurate/valid polygons.)
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        LOG = getLogger('processor.TesserocrSegmentRegion')
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        overwrite_regions = self.parameter['overwrite_regions']
        find_tables = self.parameter['find_tables']
        
        with PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            if find_tables:
                tessapi.SetVariable("textord_tabfind_find_tables", "1") # (default)
                # this should yield additional blocks within the table blocks
                # from the page iterator, but does not in fact (yet?):
                # (and it can run into assertion errors when the table structure
                #  does not meet certain homogeneity expectations)
                #tessapi.SetVariable("textord_tablefind_recognize_tables", "1")
            else:
                # disable table detection here, so tables will be
                # analysed as independent text/line blocks:
                tessapi.SetVariable("textord_tabfind_find_tables", "0")
            for (n, input_file) in enumerate(self.input_files):
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                # delete or warn of existing regions:
                if (page.get_AdvertRegion() or
                    page.get_ChartRegion() or
                    page.get_ChemRegion() or
                    page.get_GraphicRegion() or
                    page.get_ImageRegion() or
                    page.get_LineDrawingRegion() or
                    page.get_MathsRegion() or
                    page.get_MusicRegion() or
                    page.get_NoiseRegion() or
                    page.get_SeparatorRegion() or
                    page.get_TableRegion() or
                    page.get_TextRegion() or
                    page.get_UnknownRegion()):
                    if overwrite_regions:
                        LOG.info('removing existing TextRegions')
                        page.set_TextRegion([])
                        page.set_AdvertRegion([])
                        page.set_ChartRegion([])
                        page.set_ChemRegion([])
                        page.set_GraphicRegion([])
                        page.set_ImageRegion([])
                        page.set_LineDrawingRegion([])
                        page.set_MathsRegion([])
                        page.set_MusicRegion([])
                        page.set_NoiseRegion([])
                        page.set_SeparatorRegion([])
                        page.set_TableRegion([])
                        page.set_UnknownRegion([])
                    else:
                        LOG.warning('keeping existing TextRegions')
                if page.get_ReadingOrder():
                    if overwrite_regions:
                        LOG.info('overwriting existing ReadingOrder')
                        # (cannot sustain old regionrefs)
                        page.set_ReadingOrder(None)
                    else:
                        LOG.warning('keeping existing ReadingOrder')
                
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id,
                    # for some reason, external binarization
                    # degrades Tesseract segmentation quality
                    # (probably because C_OUTLINE::ComputeEdgeOffsets,
                    #  which needs the greyscale image, is more
                    #  accurate than C_OUTLINE::ComputeBinaryOffsets):
                    feature_filter='binarized')
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
                
                LOG.info("Detecting regions in page '%s'", page_id)
                tessapi.SetImage(page_image) # is already cropped to Border
                tessapi.SetPageSegMode(PSM.SPARSE_TEXT if self.parameter['sparse_text'] else PSM.AUTO)

                # detect the region segments and types:
                layout = tessapi.AnalyseLayout()
                self._process_page(layout, page, page_image, page_coords, input_file.pageId)
                
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

    def _process_page(self, it, page, page_image, page_coords, page_id):
        LOG = getLogger('processor.TesserocrSegmentRegion')
        # equivalent to GetComponentImages with raw_image=True,
        # (which would also give raw coordinates),
        # except we are also interested in the iterator's BlockType() here,
        # and its BlockPolygon()
        index = 0
        ro = page.get_ReadingOrder()
        if not ro:
            ro = ReadingOrderType()
            page.set_ReadingOrder(ro)
        og = ro.get_OrderedGroup()
        if og:
            # start counting from largest existing index
            for elem in (og.get_RegionRefIndexed() +
                         og.get_OrderedGroupIndexed() +
                         og.get_UnorderedGroupIndexed()):
                if elem.index >= index:
                    index = elem.index + 1
        else:
            # new top-level group
            og = OrderedGroupType(id="reading-order")
            ro.set_OrderedGroup(og)
        while it and not it.Empty(RIL.BLOCK):
            # (padding will be passed to both BoundingBox and GetImage)
            # (actually, Tesseract honours padding only on the left and bottom,
            #  whereas right and top are increased less!)
            bbox = it.BoundingBox(RIL.BLOCK, padding=self.parameter['padding'])
            # sometimes these polygons are not planar, which causes
            # PIL.ImageDraw.Draw.polygon (and likely others as well)
            # to misbehave; however, PAGE coordinate semantics prohibit
            # multi-path polygons!
            # (probably a bug in Tesseract itself, cf. tesseract#2826):
            if self.parameter['crop_polygons']:
                polygon = it.BlockPolygon()
            else:
                polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, page_image, page_coords)
            polygon2 = polygon_for_parent(polygon, page)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            if polygon2 is None:
                LOG.info('Ignoring extant region: %s', points)
                it.Next(RIL.BLOCK)
                continue
            # if xywh['w'] < 30 or xywh['h'] < 30:
            #     LOG.info('Ignoring too small region: %s', points)
            #     it.Next(RIL.BLOCK)
            #     continue
            # region_image_bin = it.GetBinaryImage(RIL.BLOCK)
            # if not region_image_bin.getbbox():
            #     LOG.info('Ignoring binary-empty region: %s', points)
            #     it.Next(RIL.BLOCK)
            #     continue
            #
            # add the region reference in the reading order element
            # (will be removed again if Separator/Noise region below)
            ID = "region%04d" % index
            og.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
            #
            # region type switch
            #
            block_type = it.BlockType()
            if block_type in [PT.FLOWING_TEXT,
                              PT.HEADING_TEXT,
                              PT.PULLOUT_TEXT,
                              PT.CAPTION_TEXT,
                              # TABLE is contained in PTIsTextType, but
                              # it is a bad idea to create a TextRegion
                              # for it (better set `find_tables` False):
                              # PT.TABLE,
                              # will also get a 90° @orientation
                              # (but that can be overridden by deskew/OSD):
                              PT.VERTICAL_TEXT]:
                region = TextRegionType(id=ID, Coords=coords,
                                        type=TextTypeSimpleType.PARAGRAPH)
                if block_type == PT.VERTICAL_TEXT:
                    region.set_orientation(90.0)
                elif block_type == PT.HEADING_TEXT:
                    region.set_type(TextTypeSimpleType.HEADING)
                elif block_type == PT.PULLOUT_TEXT:
                    region.set_type(TextTypeSimpleType.FLOATING)
                elif block_type == PT.CAPTION_TEXT:
                    region.set_type(TextTypeSimpleType.CAPTION)
                page.add_TextRegion(region)
                if self.parameter['sparse_text']:
                    region.set_type(TextTypeSimpleType.OTHER)
                    region.add_TextLine(TextLineType(id=region.id + '_line',
                                                     Coords=coords))
            elif block_type in [PT.FLOWING_IMAGE,
                                PT.HEADING_IMAGE,
                                PT.PULLOUT_IMAGE]:
                region = ImageRegionType(id=ID, Coords=coords)
                page.add_ImageRegion(region)
            elif block_type in [PT.HORZ_LINE,
                                PT.VERT_LINE]:
                region = SeparatorRegionType(id=ID, Coords=coords)
                page.add_SeparatorRegion(region)
                # undo appending in ReadingOrder
                og.set_RegionRefIndexed(og.get_RegionRefIndexed()[:-1])
            elif block_type in [PT.INLINE_EQUATION,
                                PT.EQUATION]:
                region = MathsRegionType(id=ID, Coords=coords)
                page.add_MathsRegion(region)
            elif block_type == PT.TABLE:
                # without API access to StructuredTable we cannot
                # do much for a TableRegionType (i.e. nrows, ncols,
                # coordinates of cells for recursive regions etc),
                # but this can be achieved afterwards by segment-table
                region = TableRegionType(id=ID, Coords=coords)
                page.add_TableRegion(region)
            else:
                region = NoiseRegionType(id=ID, Coords=coords)
                page.add_NoiseRegion()
                # undo appending in ReadingOrder
                og.set_RegionRefIndexed(og.get_RegionRefIndexed()[:-1])
            LOG.info("Detected region '%s': %s (%s)", ID, points, membername(PT, block_type))
            #
            # iterator increment
            #
            index += 1
            it.Next(RIL.BLOCK)
        if (not og.get_RegionRefIndexed() and
            not og.get_OrderedGroupIndexed() and
            not og.get_UnorderedGroupIndexed()):
            # schema forbids empty OrderedGroup
            ro.set_OrderedGroup(None)

def polygon_for_parent(polygon, parent):
    """Clip polygon to parent polygon range.
    
    (Should be moved to ocrd_utils.coordinates_for_segment.)
    """
    childp = Polygon(polygon)
    if isinstance(parent, PageType):
        if parent.get_Border():
            parentp = Polygon(polygon_from_points(parent.get_Border().get_Coords().points))
        else:
            parentp = Polygon([[0,0], [0,parent.get_imageHeight()],
                               [parent.get_imageWidth(),parent.get_imageHeight()],
                               [parent.get_imageWidth(),0]])
    else:
        parentp = Polygon(polygon_from_points(parent.get_Coords().points))
    # check if clipping is necessary
    if childp.within(parentp):
        return polygon
    # ensure input coords have valid paths (without self-intersection)
    # (this can happen when shapes valid in floating point are rounded)
    childp = make_valid(childp)
    parentp = make_valid(parentp)
    # clip to parent
    interp = childp.intersection(parentp)
    if interp.is_empty or interp.area == 0.0:
        # this happens if Tesseract "finds" something
        # outside of the valid Border of a deskewed/cropped page
        # (empty corners created by masking); will be ignored
        return None
    if interp.type == 'GeometryCollection':
        # heterogeneous result: filter zero-area shapes (LineString, Point)
        interp = unary_union([geom for geom in interp.geoms if geom.area > 0])
    if interp.type == 'MultiPolygon':
        # homogeneous result: construct convex hull to connect
        # FIXME: construct concave hull / alpha shape
        interp = interp.convex_hull
    if interp.minimum_clearance < 1.0:
        # follow-up calculations will necessarily be integer;
        # so anticipate rounding here and then ensure validity
        interp = asPolygon(np.round(interp.exterior.coords))
        interp = make_valid(interp)
    return interp.exterior.coords[:-1] # keep open

def make_valid(polygon):
    for split in range(1, len(polygon.exterior.coords)-1):
        if polygon.is_valid or polygon.simplify(polygon.area).is_valid:
            break
        # simplification may not be possible (at all) due to ordering
        # in that case, try another starting point
        polygon = Polygon(polygon.exterior.coords[-split:]+polygon.exterior.coords[:-split])
    for tolerance in range(1, int(polygon.area)):
        if polygon.is_valid:
            break
        # simplification may require a larger tolerance
        polygon = polygon.simplify(tolerance)
    return polygon
