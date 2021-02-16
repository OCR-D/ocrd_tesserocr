from __future__ import absolute_import
import os.path
from PIL import Image, ImageStat

from tesserocr import (
    RIL, PSM, OEM,
    PyTessBaseAPI, get_languages as get_languages_)

from ocrd_utils import (
    getLogger,
    make_file_id,
    assert_file_grp_cardinality,
    MIMETYPE_PAGE
)
from ocrd_models.ocrd_page import (
    TextStyleType,
    to_xml)
from ocrd_modelfactory import page_from_file
from ocrd import Processor

from .config import get_tessdata_path, OCRD_TOOL

TOOL = 'ocrd-tesserocr-fontshape'

def get_languages(*args, **kwargs):
    """
    Wraps tesserocr.get_languages() with a fixed path parameter.
    """
    return get_languages_(*args, path=get_tessdata_path(), **kwargs)

class TesserocrFontShape(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrFontShape, self).__init__(*args, **kwargs)

    def process(self):
        """Detect font shapes via rule-based OCR with Tesseract on the workspace.
        
        Open and deserialise PAGE input files and their respective images,
        then iterate over the element hierarchy down to the line level.
        
        Set up Tesseract to recognise each word's image (either from
        AlternativeImage or cropping the bounding box rectangle and masking
        it from the polygon outline) in word mode and with the ``osd`` model.
        
        Query the result's font attributes and write them into the word element's
        ``TextStyle``.
        
        Produce new output files by serialising the resulting hierarchy.
        """
        LOG = getLogger('processor.TesserocrFontShape')
        LOG.debug("TESSDATA: %s, installed Tesseract models: %s", *get_languages())

        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        model = self.parameter['model']
        if model not in get_languages()[1]:
            raise Exception("model " + model + " (needed for font style detection) is not installed")
        
        with PyTessBaseAPI(path=get_tessdata_path(),
                           #oem=OEM.TESSERACT_LSTM_COMBINED, # legacy required for OSD or WordFontAttributes!
                           oem=OEM.TESSERACT_ONLY, # legacy required for OSD or WordFontAttributes!
                           lang=model) as tessapi:
            LOG.info("Using model '%s' in %s for recognition at the word level",
                     model, get_languages()[0])
            for (n, input_file) in enumerate(self.input_files):
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if self.parameter['dpi'] > 0:
                    dpi = self.parameter['dpi']
                    LOG.info("Page '%s' images will use %d DPI from parameter override", page_id, dpi)
                elif page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
                    LOG.info("Page '%s' images will use %d DPI from image meta-data", page_id, dpi)
                else:
                    dpi = 0
                    LOG.info("Page '%s' images will use DPI estimated from segmentation", page_id)
                if dpi:
                    tessapi.SetVariable('user_defined_dpi', str(dpi))
                
                LOG.info("Processing page '%s'", page_id)
                regions = page.get_AllRegions(classes=['Text'])
                if not regions:
                    LOG.warning("Page '%s' contains no text regions", page_id)
                else:
                    self._process_regions(tessapi, regions, page_image, page_coords)
                
                file_id = make_file_id(input_file, self.output_file_grp)
                pcgts.set_pcGtsId(file_id)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_regions(self, tessapi, regions, page_image, page_coords):
        LOG = getLogger('processor.TesserocrFontShape')
        for region in regions:
            region_image, region_coords = self.workspace.image_from_segment(
                region, page_image, page_coords)
            textlines = region.get_TextLine()
            if not textlines:
                LOG.warning("Region '%s' contains no text lines", region.id)
            else:
                self._process_lines(tessapi, textlines, region_image, region_coords)

    def _process_lines(self, tessapi, textlines, region_image, region_coords):
        LOG = getLogger('processor.TesserocrFontShape')
        for line in textlines:
            line_image, line_coords = self.workspace.image_from_segment(
                line, region_image, region_coords)
            LOG.debug("Recognizing text in line '%s'", line.id)
            words = line.get_Word()
            if not words:
                LOG.warning("Line '%s' contains no words", line.id)
            else:
                self._process_words(tessapi, words, line_image, line_coords)

    def _process_words(self, tessapi, words, line_image, line_coords):
        LOG = getLogger('processor.TesserocrFontShape')
        for word in words:
            word_image, word_coords = self.workspace.image_from_segment(
                word, line_image, line_coords)
            if self.parameter['padding']:
                tessapi.SetImage(pad_image(word_image, self.parameter['padding']))
            else:
                tessapi.SetImage(word_image)
            tessapi.SetPageSegMode(PSM.SINGLE_WORD)
            #tessapi.SetPageSegMode(PSM.RAW_LINE)
            tessapi.Recognize()
            result_it = tessapi.GetIterator()
            if not result_it or result_it.Empty(RIL.WORD):
                LOG.warning("No text in word '%s'", word.id)
                continue
            LOG.debug("Decoding text in word '%s'", word.id)
            # trigger recognition
            word_text = result_it.GetUTF8Text(RIL.WORD)
            LOG.debug('Word "%s" detected "%s"', word.id, word_text)
            textequiv = word.get_TextEquiv()
            if textequiv:
                LOG.info('Word "%s" annotated "%s" / detected "%s"',
                         word.id, textequiv[0].Unicode, word_text)
            word_attributes = result_it.WordFontAttributes()
            if word_attributes:
                #LOG.debug("found font attributes: {}".format(word_attributes))
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

def pad_image(image, padding):
    stat = ImageStat.Stat(image)
    # workaround for Pillow#4925
    if len(stat.bands) > 1:
        background = tuple(stat.median)
    else:
        background = stat.median[0]
    padded = Image.new(image.mode,
                       (image.width + 2 * padding,
                        image.height + 2 * padding),
                       background)
    padded.paste(image, (padding, padding))
    return padded
