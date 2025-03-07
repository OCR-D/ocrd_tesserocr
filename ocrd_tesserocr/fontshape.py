from __future__ import absolute_import

from typing import Optional
import os.path
from PIL import Image, ImageStat

from tesserocr import (
    RIL, PSM, OEM,
    PyTessBaseAPI, 
    get_languages
)

from ocrd_models.ocrd_page import TextStyleType, OcrdPage
from ocrd.processor import OcrdPageResult

from .recognize import TesserocrRecognize
from .common import pad_image

class TesserocrFontShape(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-fontshape'

    def _init(self):
        model = self.parameter['model']
        if model not in get_languages()[1]:
            raise Exception("model " + model + " (needed for font style detection) is not installed")
        # use vanilla tesserocr API
        self.tessapi = PyTessBaseAPI(oem=OEM.TESSERACT_ONLY, # legacy required for OSD or WordFontAttributes!
                                     #oem=OEM.TESSERACT_LSTM_COMBINED,
                                     lang=model)
        self.logger.info("Using model '%s' in %s for recognition at the word level",
                         model, get_languages()[0])

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
        """Detect font shapes via rule-based OCR with Tesseract on the workspace.
        
        Open and deserialise PAGE input file and its respective images,
        then iterate over the element hierarchy down to the line level.
        
        Set up Tesseract to recognise each word's image (either from
        AlternativeImage or cropping the bounding box rectangle and masking
        it from the polygon outline) in word mode and with the ``osd`` model.
        
        Query the result's font attributes and write them into the word element's
        ``TextStyle``.
        
        Produce new output files by serialising the resulting hierarchy.
        """
        pcgts = input_pcgts[0]
        page = pcgts.get_Page()
        result = OcrdPageResult(pcgts)

        page_image, page_coords, page_image_info = self.workspace.image_from_page(
            page, page_id)
        if self.parameter['dpi'] > 0:
            dpi = self.parameter['dpi']
            self.logger.info("Page '%s' images will use %d DPI from parameter override", page_id, dpi)
        elif page_image_info.resolution != 1:
            dpi = page_image_info.resolution
            if page_image_info.resolutionUnit == 'cm':
                dpi = round(dpi * 2.54)
            self.logger.info("Page '%s' images will use %d DPI from image meta-data", page_id, dpi)
        else:
            dpi = 0
            self.logger.info("Page '%s' images will use DPI estimated from segmentation", page_id)
        self.tessapi.SetVariable('user_defined_dpi', str(dpi))

        self.logger.info("Processing page '%s'", page_id)
        regions = page.get_AllRegions(classes=['Text'])
        if not regions:
            self.logger.warning("Page '%s' contains no text regions", page_id)
        else:
            self._process_regions(regions, page_image, page_coords)

        return result

    def _process_regions(self, regions, page_image, page_coords):
        for region in regions:
            region_image, region_coords = self.workspace.image_from_segment(
                region, page_image, page_coords)
            textlines = region.get_TextLine()
            if not textlines:
                self.logger.warning("Region '%s' contains no text lines", region.id)
            else:
                self._process_lines(textlines, region_image, region_coords)

    def _process_lines(self, textlines, region_image, region_coords):
        for line in textlines:
            line_image, line_coords = self.workspace.image_from_segment(
                line, region_image, region_coords)
            self.logger.debug("Recognizing text in line '%s'", line.id)
            words = line.get_Word()
            if not words:
                self.logger.warning("Line '%s' contains no words", line.id)
            else:
                self._process_words(words, line_image, line_coords)

    def _process_words(self, words, line_image, line_coords):
        for word in words:
            word_image, word_coords = self.workspace.image_from_segment(
                word, line_image, line_coords)
            if self.parameter['padding']:
                self.tessapi.SetImage(pad_image(word_image, self.parameter['padding']))
            else:
                self.tessapi.SetImage(word_image)
            self.tessapi.SetPageSegMode(PSM.SINGLE_WORD)
            #self.tessapi.SetPageSegMode(PSM.RAW_LINE)
            self.tessapi.Recognize()
            result_it = self.tessapi.GetIterator()
            if not result_it or result_it.Empty(RIL.WORD):
                self.logger.warning("No text in word '%s'", word.id)
                continue
            self.logger.debug("Decoding text in word '%s'", word.id)
            # trigger recognition
            word_text = result_it.GetUTF8Text(RIL.WORD)
            self.logger.debug('Word "%s" detected "%s"', word.id, word_text)
            textequiv = word.get_TextEquiv()
            if textequiv:
                self.logger.info('Word "%s" annotated "%s" / detected "%s"',
                                 word.id, textequiv[0].Unicode, word_text)
            word_attributes = result_it.WordFontAttributes()
            if word_attributes:
                #self.logger.debug("found font attributes: {}".format(word_attributes))
                word_style = TextStyleType(
                    fontSize=word_attributes['pointsize']
                    if 'pointsize' in word_attributes else None,
                    fontFamily=word_attributes['font_name']
                    if 'font_name' in word_attributes else None,
                    bold=word_attributes['bold']
                    if 'bold' in word_attributes else None,
                    italic=word_attributes['italic']
                    if 'italic' in word_attributes else None,
                    underlined=word_attributes['underlined']
                    if 'underlined' in word_attributes else None,
                    monospace=word_attributes['monospace']
                    if 'monospace' in word_attributes else None,
                    serif=word_attributes['serif']
                    if 'serif' in word_attributes else None)
                word.set_TextStyle(word_style) # (or somewhere in custom attribute?)

