from __future__ import absolute_import
import tesserocr
from ocrd_utils import getLogger, concat_padded, points_from_x0y0x1y1, xywh_from_points, MIMETYPE_PAGE
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,
    OrderedGroupType,
    ReadingOrderType,
    RegionRefIndexedType,
    TextRegionType,
    ImageRegionType,
    MathsRegionType,
    SeparatorRegionType,
    NoiseRegionType,

    to_xml
)
from ocrd import Processor

from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

log = getLogger('processor.TesserocrSegmentRegion')

class TesserocrSegmentRegion(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-segment-region']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentRegion, self).__init__(*args, **kwargs)

    def process(self):
        """
        Performs the region segmentation.
        """
        with tesserocr.PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            #  print(self.input_file_grp)
            for (n, input_file) in enumerate(self.input_files):
                pcgts = page_from_file(self.workspace.download_file(input_file))
                image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)
                log.debug("Detecting regions with tesseract")
                tessapi.SetImage(image)
                # respect border element if present
                if pcgts.get_Page().get_Border() is not None and pcgts.get_Page().get_Border().get_Coords() is not None:
                    border = xywh_from_points(pcgts.get_Page().get_Border().get_Coords().points)
                    log.debug("Explictly set page border at %s", pcgts.get_Page().get_Border().get_Coords().points)
                    tessapi.SetRectangle(border['x'], border['y'], border['w'], border['h'])

                # recognize the layout and the region types
                it = tessapi.AnalyseLayout()
                index = 0
                while it and not it.Empty(tesserocr.RIL.BLOCK):
                    points = points_from_x0y0x1y1(it.BoundingBox(tesserocr.RIL.BLOCK))

                    #
                    # the region reference in the reading order element
                    #
                    ID = "region%04d" % index
                    log.debug("Detected region '%s': %s", ID, points)
                    # <pg:ReadingOrder>
                    ro = pcgts.get_Page().get_ReadingOrder()
                    if ro is None:
                        ro = ReadingOrderType()
                        pcgts.get_Page().set_ReadingOrder(ro)
                    # <pg:OrderedGroup>
                    og = ro.get_OrderedGroup()
                    if og is None:
                        og = OrderedGroupType(id="reading-order")
                        ro.set_OrderedGroup(og)
                    # <pg:RegionRefIndexed>
                    og.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))

                    #
                    # region switch
                    #
                    block_type = it.BlockType()
                    if block_type in [tesserocr.PT.FLOWING_TEXT, tesserocr.PT.HEADING_TEXT, tesserocr.PT.PULLOUT_TEXT]:
                        pcgts.get_Page().add_TextRegion(TextRegionType(id=ID, Coords=CoordsType(points=points)))
                    elif block_type in [tesserocr.PT.FLOWING_IMAGE, tesserocr.PT.HEADING_IMAGE, tesserocr.PT.PULLOUT_IMAGE]:
                        pcgts.get_Page().add_ImageRegion(ImageRegionType(id=ID, Coords=CoordsType(points=points)))
                    elif block_type in [tesserocr.PT.HORZ_LINE, tesserocr.PT.VERT_LINE]:
                        pcgts.get_Page().add_SeparatorRegion(SeparatorRegionType(id=ID, Coords=CoordsType(points=points)))
                    elif block_type in [tesserocr.PT.INLINE_EQUATION, tesserocr.PT.EQUATION]:
                        pcgts.get_Page().add_MathsRegion(MathsRegionType(id=ID, Coords=CoordsType(points=points)))
                    else:
                        pcgts.get_Page().add_NoiseRegion(NoiseRegionType(id=ID, Coords=CoordsType(points=points)))

                    #
                    # iterator increment
                    #
                    index += 1
                    it.Next(tesserocr.RIL.BLOCK)

                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename='%s/%s' % (self.output_file_grp, ID),
                    content=to_xml(pcgts).encode('utf-8'),
                )
