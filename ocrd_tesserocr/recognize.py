from __future__ import absolute_import

from tesserocr import RIL, PSM, PyTessBaseAPI, get_languages, iterate_level
from ocrd.utils import getLogger, concat_padded, xywh_from_points, points_from_x0y0x1y1
from ocrd.model.ocrd_page import from_file, to_xml, TextEquivType, CoordsType, GlyphType
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
        if self.parameter['textequiv_level'] not in ['line', 'glyph']:
            raise Exception("currently only implemented at the line/glyph level")
        model = get_languages()[1][-1] # last installed model
        if 'model' in self.parameter:
            model = self.parameter['model']
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
                        tessapi.SetPageSegMode(PSM.SINGLE_LINE)
                        #  log.debug("xywh: %s", xywh)
                        line.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text()))
                        #  tessapi.G
                        #  print(tessapi.AllWordConfidences())
                        if self.parameter['textequiv_level'] == 'glyph':
                            for word in line.get_Word():
                                log.debug("Recognizing text in word '%s'", word.id)
                                xywh = xywh_from_points(word.get_Coords().points)
                                tessapi.SetRectangle(xywh['x'], xywh['y'], xywh['w'], xywh['h'])
                                tessapi.SetPageSegMode(PSM.SINGLE_WORD)
                                word.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text()))
                                result_it = tessapi.GetIterator()
                                for (result_no, result) in enumerate(iterate_level(result_it, RIL.SYMBOL)):
                                    #symb = result.GetUTF8Text(RIL.SYMBOL) # is first choice?
                                    #conf = result.Confidence(RIL.SYMBOL) # is first choice?
                                    bbox = result.BoundingBox(RIL.SYMBOL)
                                    if bbox == None:
                                        continue
                                    glyph_id = '%s_glyph%04d' % (word.id, result_no)
                                    log.debug("Recognizing text in glyph '%s'", glyph_id)
                                    glyph = GlyphType(id=glyph_id, Coords=CoordsType(points_from_x0y0x1y1(bbox)))
                                    word.add_Glyph(glyph)
                                    choice_it = result.GetChoiceIterator()
                                    for (choice_no, choice) in enumerate(choice_it):
                                        alternative_symb = choice.GetUTF8Text()
                                        alternative_conf = choice.Confidence()
                                        glyph.add_TextEquiv(TextEquivType(index=choice_no, conf=alternative_conf, Unicode=alternative_symb))
                ID = concat_padded(self.output_file_grp, n)
                self.add_output_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts),
                )
