from __future__ import absolute_import
from tesserocr import RIL, PyTessBaseAPI, OEM, PSM
from ocrd import Processor, MIMETYPE_PAGE
from ocrd.utils import getLogger, concat_padded, points_from_xywh, polygon_from_points, xywh_from_points
from ocrd.model.ocrd_page import (
    CoordsType,
    WordType,
    from_file,
    to_xml
)

from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

log = getLogger('processor.TesserocrSegmentWord')

class TesserocrSegmentWord(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-segment-word']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentWord, self).__init__(*args, **kwargs)

    def process(self):
        """
        Performs the line segmentation.
        """
        with PyTessBaseAPI(
            psm=PSM.SINGLE_LINE,
            path=TESSDATA_PREFIX,
        ) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                pcgts = from_file(self.workspace.download_file(input_file))
                image_url = pcgts.get_Page().imageFilename
                for region in pcgts.get_Page().get_TextRegion():
                    for line in region.get_TextLine():
                        log.debug("Detecting words in line '%s'", line.id)
                        image = self.workspace.resolve_image_as_pil(image_url, polygon_from_points(line.get_Coords().points))
                        tessapi.SetImage(image)
                        offset = xywh_from_points(line.get_Coords().points)
                        for (word_no, component) in enumerate(tessapi.GetComponentImages(RIL.WORD, True)):
                            word_id = '%s_word%04d' % (line.id, word_no)
                            word_xywh = component[1]
                            word_xywh['x'] += offset['x']
                            word_xywh['y'] += offset['y']
                            line.add_Word(WordType(id=word_id, Coords=CoordsType(points_from_xywh(word_xywh))))
                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts).encode('utf-8'),
                )
