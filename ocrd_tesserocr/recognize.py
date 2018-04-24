from __future__ import absolute_import

import tesserocr
from ocrd.utils import getLogger, mets_file_id, xywh_from_coordinate_string
from ocrd.model.ocrd_page import from_file, to_xml, TextEquivType
from ocrd import Processor, MIMETYPE_PAGE
from ocrd_tesserocr.config import TESSDATA_PREFIX

log = getLogger('processor.TesserocrRecognize')

DEFAULT_MODEL = tesserocr.get_languages()[1][-1]

class TesserocrRecognize(Processor):

    def process(self):
        """
        Performs the (text) recognition.
        """
        with tesserocr.PyTessBaseAPI(path=TESSDATA_PREFIX, lang=DEFAULT_MODEL) as tessapi:
            log.info("Using model %s in %s for recognition", tesserocr.get_languages()[0], tesserocr.get_languages()[1][-1])
            tessapi.SetPageSegMode(tesserocr.PSM.SINGLE_LINE)
            for (n, input_file) in enumerate(self.input_files):
                log.info("INPUT FILE %i / %s", n, input_file)
                pcgts = from_file(self.workspace.download_file(input_file))
                image_url = pcgts.get_Page().imageFilename
                log.info("page %s", pcgts)
                for region in pcgts.get_Page().get_TextRegion():
                    textlines = region.get_TextLine()
                    log.info("About to recognize text in %i lines of region '%s'", len(textlines), region.id)
                    for (line_no, line) in enumerate(textlines):
                        log.debug("Recognizing text in region '%s' line '%s'", region.id, line_no)
                        # xTODO use binarized / gray
                        image = self.workspace.resolve_image_as_pil(image_url, xywh_from_coordinate_string(line.get_Coords().points))
                        tessapi.SetImage(image)
                        line.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text()))
                ID = mets_file_id(self.output_file_grp, n)
                self.add_output_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts).encode('utf-8'),
                )
