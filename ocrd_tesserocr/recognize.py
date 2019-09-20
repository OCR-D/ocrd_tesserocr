from __future__ import absolute_import
import os.path

from tesserocr import (
    RIL, PSM,
    PyTessBaseAPI, get_languages)

from ocrd_utils import (
    getLogger,
    concat_padded,
    points_from_polygon,
    polygon_from_x0y0x1y1,
    coordinates_for_segment,
    MIMETYPE_PAGE
)
from ocrd_models.ocrd_page import (
    CoordsType,
    GlyphType, WordType,
    LabelType, LabelsType,
    MetadataItemType,
    TextEquivType, TextStyleType,
    to_xml)
from ocrd_modelfactory import page_from_file
from ocrd import Processor

from .config import TESSDATA_PREFIX, OCRD_TOOL

TOOL = 'ocrd-tesserocr-recognize'
LOG = getLogger('processor.TesserocrRecognize')

CHOICE_THRESHOLD_NUM = 6 # maximum number of choices to query and annotate
CHOICE_THRESHOLD_CONF = 0.2 # maximum score drop from best choice to query and annotate

class TesserocrRecognize(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrRecognize, self).__init__(*args, **kwargs)

    def process(self):
        """Perform OCR recognition with Tesseract on the workspace.
        
        Open and deserialise PAGE input files and their respective images,
        then iterate over the element hierarchy down to the requested
        ``textequiv_level``. If ``overwrite_words`` is enabled and any layout
        annotation below the line level already exists, then remove it
        (regardless of ``textequiv_level``).
        Set up Tesseract to recognise each segment's image rectangle with
        the appropriate mode and ``model``. Create new elements below the line
        level if necessary. Put text results and confidence values into new
        TextEquiv at ``textequiv_level``, and make the higher levels consistent
        with that (by concatenation joined by whitespace).

        Produce new output files by serialising the resulting hierarchy.
        """
        LOG.debug("TESSDATA: %s, installed tesseract models: %s", *get_languages())
        maxlevel = self.parameter['textequiv_level']
        model = get_languages()[1][-1] # last installed model
        if 'model' in self.parameter:
            model = self.parameter['model']
            for sub_model in model.split('+'):
                if sub_model not in get_languages()[1]:
                    raise Exception("configured model " + sub_model + " is not installed")
        
        with PyTessBaseAPI(path=TESSDATA_PREFIX, lang=model) as tessapi:
            LOG.info("Using model '%s' in %s for recognition at the %s level",
                     model, get_languages()[0], maxlevel)
            # todo: populate GetChoiceIterator() with LSTM models, too:
            #tessapi.SetVariable("lstm_choice_mode", "2")
            # todo: determine relevancy of these variables:
            # tessapi.SetVariable("tessedit_single_match", "0")
            #
            # tessedit_load_sublangs
            # tessedit_preserve_min_wd_len 2
            # tessedit_prefer_joined_punct 0
            # tessedit_write_rep_codes 0
            # tessedit_parallelize 0
            # tessedit_zero_rejection 0
            # tessedit_zero_kelvin_rejection 0
            # tessedit_reject_mode 0
            # tessedit_use_reject_spaces 1
            # tessedit_fix_fuzzy_spaces 1
            # tessedit_char_blacklist
            # tessedit_char_whitelist
            # chs_leading_punct ('`"
            # chs_trailing_punct1 ).,;:?!
            # chs_trailing_punct2 )'`"
            # numeric_punctuation .,
            # unrecognised_char |
            # ok_repeated_ch_non_alphanum_wds -?*=
            # conflict_set_I_l_1 Il1[]
            # preserve_interword_spaces 0
            # tessedit_enable_dict_correction 0
            # tessedit_enable_bigram_correction 1
            # stopper_smallword_size 2
            # wordrec_max_join_chunks 4
            # suspect_space_level 100
            # suspect_short_words 2
            # language_model_ngram_on 0
            # language_model_ngram_order 8
            # language_model_min_compound_length 3
            # language_model_penalty_non_freq_dict_word 0.1
            # language_model_penalty_non_dict_word 0.15
            # language_model_penalty_punc 0.2
            # language_model_penalty_case 0.1
            # language_model_penalty_script 0.5
            # language_model_penalty_chartype 0.3
            # language_model_penalty_spacing 0.05
            # textord_max_noise_size 7
            # enable_noise_removal 1
            # classify_bln_numeric_mode 0
            # lstm_use_matrix 1
            # user_words_file
            # user_patterns_file
            for (n, input_file) in enumerate(self.input_files):
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                page = pcgts.get_Page()
                
                # add metadata about this operation and its runtime parameters:
                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=self.ocrd_tool['steps'][0],
                                     value=TOOL,
                                     Labels=[LabelsType(
                                         externalModel="ocrd-tool",
                                         externalId="parameters",
                                         Label=[LabelType(type_=name,
                                                          value=self.parameter[name])
                                                for name in self.parameter.keys()])]))
                page_image, page_xywh, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
                    tessapi.SetVariable('user_defined_dpi', str(dpi))
                #tessapi.SetImage(page_image)
                
                LOG.info("Processing page '%s'", page_id)
                regions = page.get_TextRegion()
                if not regions:
                    LOG.warning("Page '%s' contains no text regions", page_id)
                else:
                    self._process_regions(tessapi, regions, page_image, page_xywh)
                page_update_higher_textequiv_levels(maxlevel, pcgts)
                
                # Use input_file's basename for the new file -
                # this way the files retain the same basenames:
                file_id = input_file.ID.replace(self.input_file_grp, self.output_file_grp)
                if file_id == input_file.ID:
                    file_id = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_regions(self, tessapi, regions, page_image, page_xywh):
        for region in regions:
            region_image, region_xywh = self.workspace.image_from_segment(
                region, page_image, page_xywh)
            if self.parameter['textequiv_level'] == 'region':
                tessapi.SetImage(region_image)
                tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
                #if region.get_primaryScript() not in tessapi.GetLoadedLanguages()...
                LOG.debug("Recognizing text in region '%s'", region.id)
                region_text = tessapi.GetUTF8Text().rstrip("\n\f")
                region_conf = tessapi.MeanTextConf()/100.0 # iterator scores are arithmetic averages, too
                if region.get_TextEquiv():
                    LOG.warning("Region '%s' already contained text results", region.id)
                    region.set_TextEquiv([])
                # todo: consider SetParagraphSeparator
                region.add_TextEquiv(TextEquivType(Unicode=region_text, conf=region_conf))
                continue # next region (to avoid indentation below)
            ## line, word, or glyph level:
            textlines = region.get_TextLine()
            if not textlines:
                LOG.warning("Region '%s' contains no text lines", region.id)
            else:
                self._process_lines(tessapi, textlines, region_image, region_xywh)

    def _process_lines(self, tessapi, textlines, region_image, region_xywh):
        for line in textlines:
            if self.parameter['overwrite_words']:
                line.set_Word([])
            line_image, line_xywh = self.workspace.image_from_segment(
                line, region_image, region_xywh)
            # todo: Tesseract works better if the line images have a 5px margin everywhere
            tessapi.SetImage(line_image)
            # RAW_LINE fails with pre-LSTM models, but sometimes better with LSTM models
            tessapi.SetPageSegMode(PSM.SINGLE_LINE)
            #if line.get_primaryScript() not in tessapi.GetLoadedLanguages()...
            LOG.debug("Recognizing text in line '%s'", line.id)
            if self.parameter['textequiv_level'] == 'line':
                line_text = tessapi.GetUTF8Text().rstrip("\n\f")
                line_conf = tessapi.MeanTextConf()/100.0 # iterator scores are arithmetic averages, too
                if line.get_TextEquiv():
                    LOG.warning("Line '%s' already contained text results", line.id)
                    line.set_TextEquiv([])
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(Unicode=line_text, conf=line_conf))
                continue # next line (to avoid indentation below)
            ## word, or glyph level:
            words = line.get_Word()
            if words:
                ## external word layout:
                LOG.warning("Line '%s' contains words already, recognition might be suboptimal", line.id)
                self._process_existing_words(tessapi, words, line_image, line_xywh)
            else:
                ## internal word and glyph layout:
                tessapi.Recognize()
                self._process_words_in_line(tessapi.GetIterator(), line, line_xywh)

    def _process_words_in_line(self, result_it, line, line_xywh):
        if not result_it or result_it.Empty(RIL.WORD):
            LOG.warning("No text in line '%s'", line.id)
            return
        # iterate until IsAtFinalElement(RIL.LINE, RIL.WORD):
        word_no = 0
        while result_it and not result_it.Empty(RIL.WORD):
            word_id = '%s_word%04d' % (line.id, word_no)
            LOG.debug("Decoding text in word '%s'", word_id)
            bbox = result_it.BoundingBox(RIL.WORD)
            # convert to absolute coordinates:
            polygon = coordinates_for_segment(polygon_from_x0y0x1y1(bbox),
                                              None, line_xywh)
            points = points_from_polygon(polygon)
            word = WordType(id=word_id, Coords=CoordsType(points))
            line.add_Word(word)
            # todo: determine if font attributes available for word level will work with LSTM models
            word_attributes = result_it.WordFontAttributes()
            if word_attributes:
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
            # add word annotation unconditionally (i.e. even for glyph level):
            word.add_TextEquiv(TextEquivType(
                Unicode=result_it.GetUTF8Text(RIL.WORD),
                conf=result_it.Confidence(RIL.WORD)/100))
            if self.parameter['textequiv_level'] != 'word':
                self._process_glyphs_in_word(result_it, word, line_xywh)
            if result_it.IsAtFinalElement(RIL.TEXTLINE, RIL.WORD):
                break
            else:
                word_no += 1
                result_it.Next(RIL.WORD)

    def _process_existing_words(self, tessapi, words, line_image, line_xywh):
        for word in words:
            word_image, word_xywh = self.workspace.image_from_segment(
                word, line_image, line_xywh)
            tessapi.SetImage(word_image)
            tessapi.SetPageSegMode(PSM.SINGLE_WORD)
            if self.parameter['textequiv_level'] == 'word':
                LOG.debug("Recognizing text in word '%s'", word.id)
                word_text = tessapi.GetUTF8Text().rstrip("\n\f")
                word_conf = tessapi.AllWordConfidences()
                word_conf = word_conf[0]/100.0 if word_conf else 0.0
                if word.get_TextEquiv():
                    LOG.warning("Word '%s' already contained text results", word.id)
                    word.set_TextEquiv([])
                # todo: consider WordFontAttributes (TextStyle) etc (if not word.get_TextStyle())
                word.add_TextEquiv(TextEquivType(Unicode=word_text, conf=word_conf))
                continue # next word (to avoid indentation below)
            ## glyph level:
            glyphs = word.get_Glyph()
            if glyphs:
                ## external glyph layout:
                LOG.warning("Word '%s' contains glyphs already, recognition might be suboptimal", word.id)
                self._process_existing_glyphs(tessapi, glyphs, word_image, word_xywh)
            else:
                ## internal glyph layout:
                tessapi.Recognize()
                self._process_glyphs_in_word(tessapi.GetIterator(), word, word_xywh)

    def _process_existing_glyphs(self, tessapi, glyphs, word_image, word_xywh):
        for glyph in glyphs:
            glyph_image, _ = self.workspace.image_from_segment(
                glyph, word_image, word_xywh)
            tessapi.SetImage(glyph_image)
            tessapi.SetPageSegMode(PSM.SINGLE_CHAR)
            LOG.debug("Recognizing text in glyph '%s'", glyph.id)
            if glyph.get_TextEquiv():
                LOG.warning("Glyph '%s' already contained text results", glyph.id)
                glyph.set_TextEquiv([])
            #glyph_text = tessapi.GetUTF8Text().rstrip("\n\f")
            glyph_conf = tessapi.AllWordConfidences()
            glyph_conf = glyph_conf[0]/100.0 if glyph_conf else 0.0
            #LOG.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
            result_it = tessapi.GetIterator()
            if not result_it or result_it.Empty(RIL.SYMBOL):
                LOG.error("No text in glyph '%s'", glyph.id)
                continue
            choice_it = result_it.GetChoiceIterator()
            for (choice_no, choice) in enumerate(choice_it):
                alternative_text = choice.GetUTF8Text()
                alternative_conf = choice.Confidence()/100
                #LOG.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                    choice_no > CHOICE_THRESHOLD_NUM):
                    break
                # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                glyph.add_TextEquiv(TextEquivType(index=choice_no, Unicode=alternative_text, conf=alternative_conf))
    
    def _process_glyphs_in_word(self, result_it, word, word_xywh):
        if not result_it or result_it.Empty(RIL.SYMBOL):
            LOG.debug("No glyph in word '%s'", word.id)
            return
        # iterate until IsAtFinalElement(RIL.WORD, RIL.SYMBOL):
        glyph_no = 0
        while result_it and not result_it.Empty(RIL.SYMBOL):
            glyph_id = '%s_glyph%04d' % (word.id, glyph_no)
            LOG.debug("Decoding text in glyph '%s'", glyph_id)
            #  glyph_text = result_it.GetUTF8Text(RIL.SYMBOL) # equals first choice?
            glyph_conf = result_it.Confidence(RIL.SYMBOL)/100 # equals first choice?
            #LOG.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
            bbox = result_it.BoundingBox(RIL.SYMBOL)
            # convert to absolute coordinates:
            polygon = coordinates_for_segment(polygon_from_x0y0x1y1(bbox),
                                              None, word_xywh)
            points = points_from_polygon(polygon)
            glyph = GlyphType(id=glyph_id, Coords=CoordsType(points))
            word.add_Glyph(glyph)
            choice_it = result_it.GetChoiceIterator()
            for (choice_no, choice) in enumerate(choice_it):
                alternative_text = choice.GetUTF8Text()
                alternative_conf = choice.Confidence()/100
                #LOG.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                    choice_no > CHOICE_THRESHOLD_NUM):
                    break
                # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                glyph.add_TextEquiv(TextEquivType(index=choice_no, Unicode=alternative_text, conf=alternative_conf))
            if result_it.IsAtFinalElement(RIL.WORD, RIL.SYMBOL):
                break
            else:
                glyph_no += 1
                result_it.Next(RIL.SYMBOL)

def page_update_higher_textequiv_levels(level, pcgts):
    '''Update the TextEquivs of all PAGE-XML hierarchy levels above ``level`` for consistency.
    
    Starting with the hierarchy level chosen for processing,
    join all first TextEquiv (by the rules governing the respective level)
    into TextEquiv of the next higher level, replacing them.
    '''
    regions = pcgts.get_Page().get_TextRegion()
    if level != 'region':
        for region in regions:
            lines = region.get_TextLine()
            if level != 'line':
                for line in lines:
                    words = line.get_Word()
                    if level != 'word':
                        for word in words:
                            glyphs = word.get_Glyph()
                            word_unicode = u''.join(glyph.get_TextEquiv()[0].Unicode
                                                    if glyph.get_TextEquiv()
                                                    else u'' for glyph in glyphs)
                            word.set_TextEquiv(
                                [TextEquivType(Unicode=word_unicode)]) # remove old
                    line_unicode = u' '.join(word.get_TextEquiv()[0].Unicode
                                             if word.get_TextEquiv()
                                             else u'' for word in words)
                    line.set_TextEquiv(
                        [TextEquivType(Unicode=line_unicode)]) # remove old
            region_unicode = u'\n'.join(line.get_TextEquiv()[0].Unicode
                                        if line.get_TextEquiv()
                                        else u'' for line in lines)
            region.set_TextEquiv(
                [TextEquivType(Unicode=region_unicode)]) # remove old
