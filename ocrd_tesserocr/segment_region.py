from __future__ import absolute_import

import os.path
from tesserocr import (
    PyTessBaseAPI,
    PSM, RIL, PT
)

from ocrd_utils import (
    getLogger,
    concat_padded,
    points_from_x0y0x1y1,
    points_from_xywh,
    xywh_from_points,
    MIMETYPE_PAGE,
    points_from_polygon,
    membername
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    MetadataItemType,
    LabelsType, LabelType,
    CoordsType, AlternativeImageType,
    OrderedGroupType,
    ReadingOrderType,
    RegionRefIndexedType,
    TextRegionType,
    ImageRegionType,
    MathsRegionType,
    SeparatorRegionType,
    NoiseRegionType,
    to_xml)
from ocrd_models.ocrd_page_generateds import TableRegionType
from ocrd import Processor

from .config import TESSDATA_PREFIX, OCRD_TOOL

TOOL = 'ocrd-tesserocr-segment-region'
LOG = getLogger('processor.TesserocrSegmentRegion')
FALLBACK_FILEGRP_IMG = 'OCR-D-IMG-CROP'

class TesserocrSegmentRegion(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentRegion, self).__init__(*args, **kwargs)
        if hasattr(self, 'output_file_grp'):
            try:
                self.page_grp, self.image_grp = self.output_file_grp.split(',')
            except ValueError:
                self.page_grp = self.output_file_grp
                self.image_grp = FALLBACK_FILEGRP_IMG
                LOG.info("No output file group for images specified, falling back to '%s'",
                         FALLBACK_FILEGRP_IMG)

    def process(self):
        """Performs (text) region segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        and remove any existing Region and ReadingOrder elements
        (unless ``overwrite_regions`` is False).
        
        Set up Tesseract to detect blocks, and add each one to the page
        as a region according to BlockType at the detected coordinates.
        If ``find_tables`` is True, try to detect table blocks and add them
        as (atomic) TableRegion.
        
        If ``crop_polygons`` is True, create a cropped (and possibly deskewed)
        image (without extra binarization) for each region (which gets
        clipped to white outside its polygon outline), and reference th
        resulting image file as AlternativeImage in the region element.
        Add the new image to the workspace with the fileGrp USE given
        in the second position of the output fileGrp, or ``OCR-D-IMG-CROP``,
        and an ID based on input file and input element.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        overwrite_regions = self.parameter['overwrite_regions']
        find_tables = self.parameter['find_tables']
        
        with PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            if find_tables:
                tessapi.SetVariable("textord_tabfind_find_tables", "1") # (default)
                # this should yield additional blocks within the table blocks
                # from the page iterator, but does not in fact (yet?):
                tessapi.SetVariable("textord_tablefind_recognize_tables", "1")
            else:
                # disable table detection here, so tables will be
                # analysed as independent text/line blocks:
                tessapi.SetVariable("textord_tabfind_find_tables", "0")
            for (n, input_file) in enumerate(self.input_files):
                file_id = input_file.ID.replace(self.input_file_grp, self.image_grp)
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

                # delete or warn of existing regions:
                if page.get_TextRegion():
                    if overwrite_regions:
                        LOG.info('removing existing TextRegions')
                        page.set_TextRegion([])
                    else:
                        LOG.warning('keeping existing TextRegions')
                # TODO: also make non-text regions protected?
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
                if page.get_ReadingOrder():
                    if overwrite_regions:
                        LOG.info('overwriting existing ReadingOrder')
                        # (cannot sustain old regionrefs)
                        page.set_ReadingOrder(None)
                    else:
                        LOG.warning('keeping existing ReadingOrder')
                
                page_image, page_xywh, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
                    tessapi.SetVariable('user_defined_dpi', str(dpi))
                
                LOG.info("Detecting regions in page '%s'", page_id)
                tessapi.SetImage(page_image) # is already cropped to Border
                tessapi.SetPageSegMode(PSM.AUTO) # (default)

                # detect the region segments and types:
                layout = tessapi.AnalyseLayout()
                self._process_page(layout, page, page_image, page_xywh, input_file.pageId, file_id)
                
                # Use input_file's basename for the new file -
                # this way the files retain the same basenames:
                file_id = input_file.ID.replace(self.input_file_grp, self.page_grp)
                if file_id == input_file.ID:
                    file_id = concat_padded(self.page_grp, n)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.page_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.page_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_page(self, it, page, page_image, page_xywh, page_id, file_id):
        # equivalent to GetComponentImages with raw_image=True,
        # (which would also give raw coordinates),
        # except we are also interested in the iterator's BlockType() here,
        # and its BlockPolygon()
        index = 0
        while it and not it.Empty(RIL.BLOCK):
            # (padding will be passed to both BoundingBox and GetImage)
            # (actually, Tesseract honours padding only on the left and bottom,
            #  whereas right and top are increased less!)
            bbox = it.BoundingBox(RIL.BLOCK, padding=self.parameter['padding'])
            points = points_from_x0y0x1y1(bbox)
            # add offset from Border, if any:
            xywh = xywh_from_points(points)
            xywh['x'] += page_xywh['x']
            xywh['y'] += page_xywh['y']
            points = points_from_xywh(xywh)
            # sometimes these polygons are not planar, which causes
            # PIL.ImageDraw.Draw.polygon (and likely others as well)
            # to misbehave; however, PAGE coordinate semantics prohibit
            # multi-path polygons!
            # (probably a bug in Tesseract itself):
            polygon = it.BlockPolygon()
            if self.parameter['crop_polygons'] and polygon and list(polygon):
                # add offset from any Border, and
                # avoid negative results (invalid in PAGE):
                polygon = [(max(0, x + page_xywh['x']),
                            max(0, y + page_xywh['y']))
                           for x, y in polygon]
                points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
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
            # the region reference in the reading order element
            #
            ID = "region%04d" % index
            ro = page.get_ReadingOrder()
            if not ro:
                ro = ReadingOrderType()
                page.set_ReadingOrder(ro)
            og = ro.get_OrderedGroup()
            if not og:
                og = OrderedGroupType(id="reading-order")
                ro.set_OrderedGroup(og)
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
                              # should actually get a 90° @orientation
                              # (but that's ultimately for deskewing to decide):
                              PT.VERTICAL_TEXT]:
                region = TextRegionType(id=ID, Coords=coords)
                page.add_TextRegion(region)
            elif block_type in [PT.FLOWING_IMAGE,
                                PT.HEADING_IMAGE,
                                PT.PULLOUT_IMAGE]:
                region = ImageRegionType(id=ID, Coords=coords)
                page.add_ImageRegion(region)
            elif block_type in [PT.HORZ_LINE,
                                PT.VERT_LINE]:
                region = SeparatorRegionType(id=ID, Coords=coords)
                page.add_SeparatorRegion(region)
            elif block_type in [PT.INLINE_EQUATION,
                                PT.EQUATION]:
                region = MathsRegionType(id=ID, Coords=coords)
                page.add_MathsRegion(region)
            elif block_type == PT.TABLE:
                # without API access to StructuredTable we cannot
                # do much for a TableRegionType (i.e. nrows, ncols,
                # coordinates of cells for recursive regions etc),
                # but this could be achieved later by a specialised
                # processor
                region = TableRegionType(id=ID, Coords=coords)
                page.add_TableRegion(region)
            else:
                region = NoiseRegionType(id=ID, Coords=coords)
                page.add_NoiseRegion()
            LOG.info("Detected region '%s': %s (%s)", ID, points, membername(PT, block_type))
            if self.parameter['crop_polygons']:
                # Store the cropped (and deskewed) image for the region,
                # this is not always preferable, because Tesseract tends
                # to produce polygon outlines that are worse than the
                # enclosing bounding boxes, and these are always used
                # as mask for the image (see above). Also, it chops off
                # corners when rotating against the recognised skew.
                # Moreover, the mix of colour and white background
                # in these images might cause binarization trouble.
                # (Although against the latter we could switch to
                #  GetBinaryImage).
                # You have been warned!
                # get the raw image (masked by white space along the block polygon):
                region_image, _, _ = it.GetImage(RIL.BLOCK, self.parameter['padding'], page_image)
                page_xywh['features'] += ',cropped'
                # update METS (add the image file):
                file_path = self.workspace.save_image_file(region_image,
                                            file_id + '_' + ID,
                                            page_id=page_id,
                                            file_grp=self.image_grp)
                # update PAGE (reference the image file):
                region.add_AlternativeImage(AlternativeImageType(
                    filename=file_path, comments=page_xywh['features']))
            #
            # iterator increment
            #
            index += 1
            it.Next(RIL.BLOCK)
