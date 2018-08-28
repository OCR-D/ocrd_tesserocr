from __future__ import absolute_import
from tesserocr import PyTessBaseAPI, RIL
from ocrd import Processor, MIMETYPE_PAGE
from ocrd.utils import getLogger, concat_padded, points_from_xywh, polygon_from_points, xywh_from_points
from ocrd.model.ocrd_page import (
    CoordsType,
    TextLineType,
    from_file,
    to_xml
)

from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

log = getLogger('processor.TesserocrSegmentLine')

class TesserocrSegmentLine(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-segment-line']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentLine, self).__init__(*args, **kwargs)


    def process(self):
        """
        Performs the line segmentation.
        """
        with PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                pcgts = from_file(self.workspace.download_file(input_file))
                image_url = pcgts.get_Page().imageFilename
                for region in pcgts.get_Page().get_TextRegion():
                    log.debug("Detecting lines in %s with tesseract", region.id)
                    image = self.workspace.resolve_image_as_pil(image_url, polygon_from_points(region.get_Coords().points))
                    tessapi.SetImage(image)
                    offset = xywh_from_points(region.get_Coords().points)
                    for (line_no, component) in enumerate(tessapi.GetComponentImages(RIL.TEXTLINE, True)):
                        line_id = '%s_line%04d' % (region.id, line_no)
                        line_xywh = component[1]
                        line_xywh['x'] += offset['x']
                        line_xywh['y'] += offset['y']
                        line_points = points_from_xywh(line_xywh)
                        region.add_TextLine(TextLineType(id=line_id, Coords=CoordsType(line_points)))
                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts).encode('utf-8'),
                )
