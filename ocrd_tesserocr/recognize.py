from __future__ import absolute_import

from tesserocr import PyTessBaseAPI, get_languages
from ocrd.utils import getLogger, concat_padded, xywh_from_points
from ocrd.model.ocrd_page import from_file, to_xml, TextEquivType
from ocrd import Processor, MIMETYPE_PAGE
from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

log = getLogger('processor.TesserocrRecognize')

class TesserocrRecognize(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-recognize']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrRecognize, self).__init__(*args, **kwargs)

    def process(self):
        """
        Performs the (text) recognition.
        """
        print(self.parameter)
        if self.parameter['textequiv_level'] != 'line':
            raise Exception("currently only implemented at the line level")
        model = get_languages()[1][-1] # last installed model
        if 'language' in self.parameter:
            model = self.parameter['language']
            if model not in get_languages()[1]:
                raise Exception("configured model " + model + " is not installed")
        with PyTessBaseAPI(path=TESSDATA_PREFIX, lang=model) as tessapi:
            log.info("Using model %s in %s for recognition", model, get_languages()[0])
            for (n, input_file) in enumerate(self.input_files):
                log.info("INPUT FILE %i / %s", n, input_file)
                pcgts = from_file(self.workspace.download_file(input_file))
                # TODO use binarized / gray
                pil_image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)
                tessapi.SetImage(pil_image)
                # TODO slow
                #  tessapi.SetPageSegMode(PSM.SINGLE_LINE)
                log.info("page %s", pcgts)
                for region in pcgts.get_Page().get_TextRegion():
                    textlines = region.get_TextLine()
                    log.info("About to recognize text in %i lines of region '%s'", len(textlines), region.id)
                    for line in textlines:
                        log.debug("Recognizing text in line '%s'", line.id)
                        xywh = xywh_from_points(line.get_Coords().points)
                        tessapi.SetRectangle(xywh['x'], xywh['y'], xywh['w'], xywh['h'])
                        #  log.debug("xywh: %s", xywh)
                        line.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text()))
                        #  tessapi.G
                        #  print(tessapi.AllWordConfidences())
                ID = concat_padded(self.output_file_grp, n)
                self.add_output_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts),
                )
