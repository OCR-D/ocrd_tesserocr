from __future__ import absolute_import
import tesserocr
from ocrd.utils import getLogger, mets_file_id
from ocrd import Processor, MIMETYPE_PAGE
from ocrd_tesserocr.config import TESSDATA_PREFIX
from ocrd.utils import getLogger, mets_file_id, coordinate_string_from_xywh, xywh_from_coordinate_string
from ocrd.model.ocrd_page import (
    ReadingOrderType,
    RegionRefIndexedType,
    TextRegionType,
    CoordsType,
    TextLineType,
    OrderedGroupType,
    from_file,
    to_xml
)

log = getLogger('processor.TesserocrSegmentLine')

class TesserocrSegmentLine(Processor):

    def process(self):
        """
        Performs the line segmentation.
        """
        with tesserocr.PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                pcgts = from_file(self.workspace.download_file(input_file))
                image_url = pcgts.get_Page().imageFilename
                for region in pcgts.get_Page().get_TextRegion():
                    log.debug("Detecting lines in %s with tesseract", region)
                    image = self.workspace.resolve_image_as_pil(image_url, xywh_from_coordinate_string(region.get_Coords().points))
                    tessapi.SetImage(image)
                    for (line_no, component) in enumerate(tessapi.GetComponentImages(tesserocr.RIL.TEXTLINE, True)):
                        line_id = '%sl%s' % (region.id, line_no)
                        region.add_TextLine(TextLineType(id=line_id, Coords=CoordsType(coordinate_string_from_xywh(component[1]))))
                ID = mets_file_id(self.output_file_grp, n)
                self.add_output_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts).encode('utf-8'),
                )
