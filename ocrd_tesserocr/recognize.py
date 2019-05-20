from __future__ import absolute_import
import math

from tesserocr import (
    RIL, PSM,
    PyTessBaseAPI, get_languages,
    Orientation, TextlineOrder, WritingDirection)

from ocrd_utils import (
    getLogger, concat_padded,
    polygon_from_points, xywh_from_points, points_from_x0y0x1y1,
    MIMETYPE_PAGE)
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

log = getLogger('processor.TesserocrRecognize')

CHOICE_THRESHOLD_NUM = 6 # maximum number of choices to query and annotate
CHOICE_THRESHOLD_CONF = 0.2 # maximum score drop from best choice to query and annotate
MAX_ELEMENTS = 500 # maximum number of lower level elements embedded within each element (for word/glyph iterators)

class TesserocrRecognize(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-recognize']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrRecognize, self).__init__(*args, **kwargs)

    def process(self):
        """Perform OCR recognition with Tesseract on the workspace.
        
        Open and deserialise PAGE input files and their respective images, 
        then iterate over the element hierarchy down to the requested
        `textequiv_level`. If `overwrite_words` is enabled and any layout
        annotation below the line level already exists, then remove it
        (regardless of `textequiv_level`).
        Set up Tesseract to recognise each segment's image rectangle with
        the appropriate mode and `model`. Create new elements below the line
        level if necessary. Put text results and confidence values into new
        TextEquiv at `textequiv_level`, and make the higher levels consistent
        with that (by concatenation joined by whitespace). Produce new output
        files by serialising the resulting hierarchy.
        """
        log.debug("TESSDATA: %s, installed tesseract models: %s", *get_languages())
        maxlevel = self.parameter['textequiv_level']
        model = get_languages()[1][-1] # last installed model
        if 'model' in self.parameter:
            model = self.parameter['model']
            if model not in get_languages()[1]:
                raise Exception("configured model " + model + " is not installed")
        with PyTessBaseAPI(path=TESSDATA_PREFIX, lang=model) as tessapi:
            log.info("Using model '%s' in %s for recognition at the %s level", model, get_languages()[0], maxlevel)
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
                log.info("INPUT FILE %i / %s", n, input_file)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                # TODO use binarized / gray
                pil_image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)
                tessapi.SetImage(pil_image)
                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=OCRD_TOOL['tools']['ocrd-tesserocr-recognize']['steps'][0],
                                     value='ocrd-tesserocr-recognize',
                                     # FIXME: externalRef is invalid by pagecontent.xsd, but ocrd does not reflect this
                                     # what we want here is `externalModel="ocrd-tool" externalId="parameters"`
                                     Labels=[LabelsType(#externalRef="parameters",
                                                        Label=[LabelType(type_=name,
                                                                         value=self.parameter[name])
                                                               for name in self.parameter.keys()])]))
                log.info("Recognizing text in page '%s'", pcgts.get_pcGtsId())
                regions = pcgts.get_Page().get_TextRegion()
                if not regions:
                    log.warning("Page contains no text regions")
                self._process_regions(regions, maxlevel, tessapi)
                page_update_higher_textequiv_levels(maxlevel, pcgts)
                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename='%s/%s' % (self.output_file_grp, ID),
                    content=to_xml(pcgts),
                )

    def _process_regions(self, regions, maxlevel, tessapi):
        for region in regions:
            log.debug("Recognizing text in region '%s'", region.id)
            # todo: determine if and how this can still be used for region classification:
            # result_it = tessapi.GetIterator()
            # if not result_it or result_it.Empty(RIL.BLOCK)
            # ptype = result_it.BlockType()
            # PT.UNKNOWN
            # PT.FLOWING_TEXT
            # PT.HEADING_TEXT
            # PT.PULLOUT_TEXT
            # PT.EQUATION
            # PT.TABLE
            # PT.VERTICAL_TEXT
            # PT.CAPTION_TEXT
            # PT.HORZ_LINE
            # PT.VERT_LINE
            # PT.NOISE
            # PT.COUNT
            # ...
            if maxlevel == 'region':
                region_xywh = xywh_from_points(region.get_Coords().points)
                tessapi.SetRectangle(region_xywh['x'], region_xywh['y'], region_xywh['w'], region_xywh['h'])
                tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
                region_text = tessapi.GetUTF8Text().rstrip("\n\f")
                region_conf = tessapi.MeanTextConf()/100.0 # iterator scores are arithmetic averages, too
                if region.get_TextEquiv():
                    log.warning("Region '%s' already contained text results", region.id)
                    region.set_TextEquiv([])
                # todo: consider SetParagraphSeparator
                region.add_TextEquiv(TextEquivType(Unicode=region_text, conf=region_conf))
                continue # next region (to avoid indentation below)
            ## line, word, or glyph level:
            textlines = region.get_TextLine()
            if not textlines:
                log.warning("Region '%s' contains no text lines", region.id)
            else:
                self._process_lines(textlines, maxlevel, tessapi)

    def _process_lines(self, textlines, maxlevel, tessapi):
        for line in textlines:
            if self.parameter['overwrite_words']:
                line.set_Word([])
            log.debug("Recognizing text in line '%s'", line.id)
            line_xywh = xywh_from_points(line.get_Coords().points)
            #  log.debug("xywh: %s", line_xywh)
            tessapi.SetRectangle(line_xywh['x'], line_xywh['y'], line_xywh['w'], line_xywh['h'])
            tessapi.SetPageSegMode(PSM.SINGLE_LINE) # RAW_LINE fails with Tesseract 3 models and is worse with Tesseract 4 models
            if maxlevel == 'line':
                line_text = tessapi.GetUTF8Text().rstrip("\n\f")
                line_conf = tessapi.MeanTextConf()/100.0 # iterator scores are arithmetic averages, too
                if line.get_TextEquiv():
                    log.warning("Line '%s' already contained text results", line.id)
                    line.set_TextEquiv([])
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(Unicode=line_text, conf=line_conf))
                continue # next line (to avoid indentation below)
            ## word, or glyph level:
            words = line.get_Word()
            if words:
                ## external word layout:
                log.warning("Line '%s' contains words already, recognition might be suboptimal", line.id)
                self._process_existing_words(words, maxlevel, tessapi)
            else:
                ## internal word and glyph layout:
                tessapi.Recognize()
                self._process_words_in_line(line, maxlevel, tessapi.GetIterator())

    def _process_words_in_line(self, line, maxlevel, result_it):
        for word_no in range(0, MAX_ELEMENTS): # iterate until IsAtFinalElement(RIL.LINE, RIL.WORD)
            if not result_it:
                log.error("No iterator at '%s'", line.id)
                break
            if result_it.Empty(RIL.WORD):
                log.warning("No word in line '%s'", line.id)
                break
            word_id = '%s_word%04d' % (line.id, word_no)
            log.debug("Recognizing text in word '%s'", word_id)
            word_bbox = result_it.BoundingBox(RIL.WORD)
            word = WordType(id=word_id, Coords=CoordsType(points_from_x0y0x1y1(word_bbox)))
            line.add_Word(word)
            # todo: determine if font attributes available for word level will work with LSTM models
            word_attributes = result_it.WordFontAttributes()
            if word_attributes:
                word_style = TextStyleType(fontSize=word_attributes['pointsize'] if 'pointsize' in word_attributes else None,
                                           fontFamily=word_attributes['font_name'] if 'font_name' in word_attributes else None,
                                           bold=None if 'bold' not in word_attributes else word_attributes['bold'],
                                           italic=None if 'italic' not in word_attributes else word_attributes['italic'],
                                           underlined=None if 'underlined' not in word_attributes else word_attributes['underlined'],
                                           monospace=None if 'monospace' not in word_attributes else word_attributes['monospace'],
                                           serif=None if 'serif' not in word_attributes else word_attributes['serif']
                                           )
                word.set_TextStyle(word_style) # (or somewhere in custom attribute?)
            # add word annotation unconditionally (i.e. even for glyph level):
            word.add_TextEquiv(TextEquivType(Unicode=result_it.GetUTF8Text(RIL.WORD), conf=result_it.Confidence(RIL.WORD)/100))
            if maxlevel == 'word':
                pass
            else:
                self._process_glyphs_in_word(word, result_it)
            if result_it.IsAtFinalElement(RIL.TEXTLINE, RIL.WORD):
                break
            else:
                result_it.Next(RIL.WORD)

    def _process_existing_words(self, words, maxlevel, tessapi):
        for word in words:
            log.debug("Recognizing text in word '%s'", word.id)
            word_xywh = xywh_from_points(word.get_Coords().points)
            tessapi.SetRectangle(word_xywh['x'], word_xywh['y'], word_xywh['w'], word_xywh['h'])
            tessapi.SetPageSegMode(PSM.SINGLE_WORD)
            if maxlevel == 'word':
                word_text = tessapi.GetUTF8Text().rstrip("\n\f")
                word_conf = tessapi.AllWordConfidences()
                word_conf = word_conf[0]/100.0 if word_conf else 0.0
                if word.get_TextEquiv():
                    log.warning("Word '%s' already contained text results", word.id)
                    word.set_TextEquiv([])
                # todo: consider WordFontAttributes (TextStyle) etc (if not word.get_TextStyle())
                word.add_TextEquiv(TextEquivType(Unicode=word_text, conf=word_conf))
                continue # next word (to avoid indentation below)
            ## glyph level:
            glyphs = word.get_Glyph()
            if glyphs:
                ## external glyph layout:
                log.warning("Word '%s' contains glyphs already, recognition might be suboptimal", word.id)
                self._process_existing_glyphs(glyphs, tessapi)
            else:
                ## internal glyph layout:
                tessapi.Recognize()
                self._process_glyphs_in_word(word, tessapi.GetIterator())

    def _process_existing_glyphs(self, glyphs, tessapi):
        for glyph in glyphs:
            log.debug("Recognizing glyph in word '%s'", glyph.id)
            glyph_xywh = xywh_from_points(glyph.get_Coords().points)
            tessapi.SetRectangle(glyph_xywh['x'], glyph_xywh['y'], glyph_xywh['w'], glyph_xywh['h'])
            tessapi.SetPageSegMode(PSM.SINGLE_CHAR)
            if glyph.get_TextEquiv():
                log.warning("Glyph '%s' already contained text results", glyph.id)
                glyph.set_TextEquiv([])
            #glyph_text = tessapi.GetUTF8Text().rstrip("\n\f")
            glyph_conf = tessapi.AllWordConfidences()
            glyph_conf = glyph_conf[0]/100.0 if glyph_conf else 0.0
            #log.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
            result_it = tessapi.GetIterator()
            if not result_it or result_it.Empty(RIL.SYMBOL):
                log.error("No glyph here")
                continue
            choice_it = result_it.GetChoiceIterator()
            for (choice_no, choice) in enumerate(choice_it):
                alternative_text = choice.GetUTF8Text()
                alternative_conf = choice.Confidence()/100
                #log.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                    choice_no > CHOICE_THRESHOLD_NUM):
                    break
                # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                glyph.add_TextEquiv(TextEquivType(index=choice_no, Unicode=alternative_text, conf=alternative_conf))
    
    def _process_glyphs_in_word(self, word, result_it):
        for glyph_no in range(0, MAX_ELEMENTS): # iterate until IsAtFinalElement(RIL.WORD, RIL.SYMBOL)
            if not result_it:
                log.error("No iterator at '%s'", word.id)
                break
            if result_it.Empty(RIL.SYMBOL):
                log.debug("No glyph here")
                break
            glyph_id = '%s_glyph%04d' % (word.id, glyph_no)
            log.debug("Recognizing text in glyph '%s'", glyph_id)
            #  glyph_text = result_it.GetUTF8Text(RIL.SYMBOL) # equals first choice?
            glyph_conf = result_it.Confidence(RIL.SYMBOL)/100 # equals first choice?
            #log.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
            glyph_bbox = result_it.BoundingBox(RIL.SYMBOL)
            glyph = GlyphType(id=glyph_id, Coords=CoordsType(points_from_x0y0x1y1(glyph_bbox)))
            word.add_Glyph(glyph)
            choice_it = result_it.GetChoiceIterator()
            for (choice_no, choice) in enumerate(choice_it):
                alternative_text = choice.GetUTF8Text()
                alternative_conf = choice.Confidence()/100
                #log.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                    choice_no > CHOICE_THRESHOLD_NUM):
                    break
                # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                glyph.add_TextEquiv(TextEquivType(index=choice_no, Unicode=alternative_text, conf=alternative_conf))
            if result_it.IsAtFinalElement(RIL.WORD, RIL.SYMBOL):
                break
            else:
                result_it.Next(RIL.SYMBOL)

def page_update_higher_textequiv_levels(level, pcgts):
    '''Update the TextEquivs of all PAGE-XML hierarchy levels above `level` for consistency.
    
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
