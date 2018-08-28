from __future__ import absolute_import
import tesserocr
from ocrd.utils import getLogger, concat_padded, points_from_xywh
from ocrd.model.ocrd_page import (
    ReadingOrderType,
    RegionRefIndexedType,
    TextRegionType,
    CoordsType,
    OrderedGroupType,
    from_file,
    to_xml
)
from ocrd import Processor, MIMETYPE_PAGE

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
            print(self.input_file_grp)
            for (n, input_file) in enumerate(self.input_files):
                pcgts = from_file(self.workspace.download_file(input_file))
                image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)
                log.debug("Detecting regions with tesseract")
                tessapi.SetImage(image)
                for component in tessapi.GetComponentImages(tesserocr.RIL.BLOCK, True):
                    points, index = points_from_xywh(component[1]), component[2]

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
                    #  text region
                    #
                    pcgts.get_Page().add_TextRegion(TextRegionType(id=ID, Coords=CoordsType(points=points)))

                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts).encode('utf-8'),
                )
