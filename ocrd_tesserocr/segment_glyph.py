from __future__ import absolute_import
from tesserocr import RIL, PyTessBaseAPI, PSM
from ocrd import Processor, MIMETYPE_PAGE
from ocrd_tesserocr.config import TESSDATA_PREFIX
from ocrd.utils import getLogger, mets_file_id, points_from_xywh, xywh_from_points
from ocrd.model.ocrd_page import (
    CoordsType,
    GlyphType,
    from_file,
    to_xml
)

log = getLogger('processor.TesserocrSegmentGlyph')

class TesserocrSegmentGlyph(Processor):

    def process(self):
        """
        Performs the line segmentation.
        """
        with PyTessBaseAPI(
            path=TESSDATA_PREFIX,
        ) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                pcgts = from_file(self.workspace.download_file(input_file))
                image_url = pcgts.get_Page().imageFilename
                tessapi.SetImage(self.workspace.resolve_image_as_pil(image_url))
                for region in pcgts.get_Page().get_TextRegion():
                    for line in region.get_TextLine():
                        for word in line.get_Word():
                            xywh = xywh_from_points(word.get_Coords().points)
                            tessapi.SetRectangle(xywh['x'], xywh['y'], xywh['w'], xywh['h'])
                            log.debug("Segmenting glyphs in word '%s'", word.id)
                            offset = xywh_from_points(word.get_Coords().points)
                            for (glyph_no, component) in enumerate(tessapi.GetComponentImages(RIL.SYMBOL, True)):
                                glyph_id = '%s_glyph%04d' % (line.id, glyph_no)
                                glyph_xywh = component[1]
                                glyph_xywh['x'] += offset['x']
                                glyph_xywh['y'] += offset['y']
                                word.add_Glyph(GlyphType(id=glyph_id, Coords=CoordsType(points_from_xywh(glyph_xywh))))
                ID = mets_file_id(self.output_file_grp, n)
                self.add_output_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts).encode('utf-8'),
                )
