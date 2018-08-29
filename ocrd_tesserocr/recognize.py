from __future__ import absolute_import

from tesserocr import RIL, PSM, PyTessBaseAPI, PyResultIterator, get_languages, iterate_level
from ocrd.utils import getLogger, concat_padded, xywh_from_points, points_from_xywh, points_from_x0y0x1y1
from ocrd.model.ocrd_page import from_file, to_xml, TextEquivType, CoordsType, GlyphType, WordType
from ocrd.model.ocrd_page_generateds import TextStyleType, MetadataItemType, LabelsType, LabelType
from ocrd import Processor, MIMETYPE_PAGE
from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

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
        """
        Performs the (text) recognition.
        """
        # print(self.parameter)
        maxlevel = self.parameter['textequiv_level']
        model = get_languages()[1][-1] # last installed model
        if 'model' in self.parameter:
            model = self.parameter['model']
            if model not in get_languages()[1]:
                raise Exception("configured model " + model + " is not installed")
        with PyTessBaseAPI(path=TESSDATA_PREFIX, lang=model) as tessapi:
            log.info("Using model '%s' in %s for recognition at the %s level", model, get_languages()[0], maxlevel)
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
                pcgts = from_file(self.workspace.download_file(input_file))
                # TODO use binarized / gray
                pil_image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)
                tessapi.SetImage(pil_image)
                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=OCRD_TOOL['tools']['ocrd-tesserocr-recognize']['steps'][0],
                                     value='ocrd-tesserocr-recognize',
                                     Labels=[LabelsType(externalRef="parameters",
                                                        Label=[LabelType(type_=name,
                                                                         value=self.parameter[name])
                                                               for name in self.parameter.keys()])]))
                # TODO slow
                #  tessapi.SetPageSegMode(PSM.SINGLE_LINE)
                log.info("Recognizing text in page '%s'", pcgts.get_pcGtsId())
                page = pcgts.get_Page()
                if maxlevel == 'page':
                    # not sure what to do here: 
                    # - We cannot simply do GetUTF8Text(), because there is no TextEquiv on the page level.
                    # - We could GetComponentImages(RIL.BLOCK) and add a text region for each, then enter region level recognition below. But what if regions are already annotated? How to go about non-text blocks?
                    raise Exception("currently only implemented below the page level")
                ## region, line, word, or glyph level:
                regions = page.get_TextRegion()
                if not regions:
                    log.warn("Page contains no text regions") 
                for region in regions:
                    log.debug("Recognizing text in region '%s'", region.id)
                    if maxlevel == 'region':
                        region_xywh = xywh_from_points(region.get_Coords().points)
                        tessapi.SetRectangle(region_xywh['x'], region_xywh['y'], region_xywh['w'], region_xywh['h'])
                        tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
                        if region.get_TextEquiv():
                            log.warn("Region '%s' already contains text results", region.id)
                        region.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text().rstrip("\n\f")))
                        continue # next region (to avoid indentation below)
                    ## line, word, or glyph level:
                    textlines = region.get_TextLine()
                    if not textlines:
                        log.warn("Region '%s' contains no text lines", region.id)
                    for line in textlines:
                        log.debug("Recognizing text in line '%s'", line.id)
                        line_xywh = xywh_from_points(line.get_Coords().points)
                        #  log.debug("xywh: %s", line_xywh)
                        tessapi.SetRectangle(line_xywh['x'], line_xywh['y'], line_xywh['w'], line_xywh['h'])
                        tessapi.SetPageSegMode(PSM.SINGLE_LINE) # RAW_LINE fails with Tesseract 3 models and is worse with Tesseract 4 models
                        if line.get_TextEquiv():
                            log.warn("Line '%s' already contains text results", line.id)
                        #  tessapi.G
                        line_conf = 1.0
                        for (word_no, conf) in enumerate(tessapi.AllWordConfidences()): # or tessapi.MeanTextConf()?
                            line_conf *= conf/100.0
                        # add line annotation unconditionally (i.e. even for word or glyph level):
                        line.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text().rstrip("\n\f"), conf=line_conf))
                        if maxlevel == 'line':
                            # maybe add TextEquiv alternatives via ChoiceIterator for TEXTLINE?
                            continue # next line (to avoid indentation below)
                        ## word, or glyph level:
                        words = line.get_Word()
                        if words:
                            ## external word layout:
                            # raise Exception("existing annotation for Word level would clash with OCR results for line '%s'", line.id) # forcing external layout annotation for words or glyphs is worse with Tesseract
                            log.warn("Line '%s' contains words already, recognition might be suboptimal", line.id)
                            for word in words:
                                log.debug("Recognizing word in line '%s'", word.id)
                                word_xywh = xywh_from_points(word.get_Coords().points)
                                tessapi.SetRectangle(word_xywh['x'], word_xywh['y'], word_xywh['w'], word_xywh['h'])
                                tessapi.SetPageSegMode(PSM.SINGLE_WORD)
                                if word.get_TextEquiv():
                                    log.warn("Word '%s' already contains text results", word.id)
                                word_conf = tessapi.AllWordConfidences()[0]/100.0
                                word.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text().rstrip("\n\f"), conf=word_conf))
                                if maxlevel == 'word':
                                    # maybe add TextEquiv alternatives via ChoiceIterator for WORD?
                                    continue # next word (to avoid indentation below)
                                ## glyph level:
                                glyphs = word.get_Glyph()
                                if glyphs:
                                    ## external glyph layout:
                                    # raise Exception("existing annotation for Glyph level would clash with OCR results for word '%s'", word.id) # forcing external layout annotation for gylphs is worse with Tesseract
                                    log.warn("Word '%s' contains glyphs already, recognition might be suboptimal", word.id)
                                    for glyph in glyphs:
                                        log.debug("Recognizing glyph in word '%s'", glyph.id)
                                        glyph_xywh = xywh_from_points(glyph.get_Coords().points)
                                        tessapi.SetRectangle(glyph_xywh['x'], glyph_xywh['y'], glyph_xywh['w'], glyph_xywh['h'])
                                        tessapi.SetPageSegMode(PSM.SINGLE_CHAR)
                                        if glyph.get_TextEquiv():
                                            log.warn("Glyph '%s' already contains text results", glyph.id)
                                        glyph_conf = tessapi.AllWordConfidences()[0]/100.0
                                        glyph.add_TextEquiv(TextEquivType(Unicode=tessapi.GetUTF8Text().rstrip("\n\f"), conf=glyph_conf))
                                        # maybe add TextEquiv alternatives via ChoiceIterator for SYMBOL?
                                    continue # next word (to avoid indentation below)
                                ## internal glyph layout:
                                result_it = tessapi.GetIterator()
                                for glyph_no in range(0,MAX_ELEMENTS): # iterate until IsAtFinalElement(RIL.WORD, RIL.SYMBOL)
                                    if result_it.Empty(RIL.SYMBOL):
                                        log.debug("No glyph here")
                                        break
                                    glyph_id = '%s_glyph%04d' % (word.id, glyph_no)
                                    log.debug("Recognizing text in glyph '%s'", glyph_id)
                                    glyph_symb = result_it.GetUTF8Text(RIL.SYMBOL) # equals first choice?
                                    glyph_conf = result_it.Confidence(RIL.SYMBOL)/100 # equals first choice?
                                    glyph_bbox = result_it.BoundingBox(RIL.SYMBOL)
                                    glyph = GlyphType(id=glyph_id, Coords=CoordsType(points_from_x0y0x1y1(glyph_bbox)))
                                    word.add_Glyph(glyph)
                                    choice_it = result_it.GetChoiceIterator()
                                    for (choice_no, choice) in enumerate(choice_it):
                                        alternative_symb = choice.GetUTF8Text()
                                        alternative_conf = choice.Confidence()/100
                                        if (glyph_conf-alternative_conf > CHOICE_THRESHOLD_CONF or
                                            choice_no > CHOICE_THRESHOLD_NUM):
                                            break
                                        glyph.add_TextEquiv(TextEquivType(index=choice_no, conf=alternative_conf, Unicode=alternative_symb))
                                    if result_it.IsAtFinalElement(RIL.WORD, RIL.SYMBOL):
                                        break
                                    else:
                                        result_it.Next(RIL.SYMBOL)
                            continue # next line (to avoid indentation below)
                        ## internal word and glyph layout:
                        result_it = tessapi.GetIterator()
                        for word_no in range(0,MAX_ELEMENTS): # iterate until IsAtFinalElement(RIL.LINE, RIL.WORD)
                            if result_it.Empty(RIL.WORD):
                                log.debug("No word here")
                                break
                            word_id = '%s_word%04d' % (line.id, word_no)
                            log.debug("Recognizing text in word '%s'", word_id)
                            word_bbox = result_it.BoundingBox(RIL.WORD)
                            word = WordType(id=word_id, Coords=CoordsType(points_from_x0y0x1y1(word_bbox)))
                            line.add_Word(word)
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
                            # word_type = result_it.BlockType()
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
                            # add word annotation unconditionally (i.e. even for glyph level):
                            word.add_TextEquiv(TextEquivType(Unicode=result_it.GetUTF8Text(RIL.WORD), conf=result_it.Confidence(RIL.WORD)/100))
                            if maxlevel == 'word':
                                # maybe add TextEquiv alternatives via ChoiceIterator for WORD?
                                pass
                            else:
                                ## glyph level:
                                for glyph_no in range(0,MAX_ELEMENTS): # iterate until IsAtFinalElement(RIL.WORD, RIL.SYMBOL)
                                    if result_it.Empty(RIL.SYMBOL):
                                        log.debug("No glyph here")
                                        break
                                    glyph_id = '%s_glyph%04d' % (word.id, glyph_no)
                                    log.debug("Recognizing text in glyph '%s'", glyph_id)
                                    glyph_symb = result_it.GetUTF8Text(RIL.SYMBOL) # equals first choice?
                                    glyph_conf = result_it.Confidence(RIL.SYMBOL)/100 # equals first choice?
                                    glyph_bbox = result_it.BoundingBox(RIL.SYMBOL)
                                    glyph = GlyphType(id=glyph_id, Coords=CoordsType(points_from_x0y0x1y1(glyph_bbox)))
                                    word.add_Glyph(glyph)
                                    choice_it = result_it.GetChoiceIterator()
                                    for (choice_no, choice) in enumerate(choice_it):
                                        alternative_symb = choice.GetUTF8Text()
                                        alternative_conf = choice.Confidence()/100
                                        if (glyph_conf-alternative_conf > CHOICE_THRESHOLD_CONF or
                                            choice_no > CHOICE_THRESHOLD_NUM):
                                            break
                                        glyph.add_TextEquiv(TextEquivType(index=choice_no, conf=alternative_conf, Unicode=alternative_symb))
                                    if result_it.IsAtFinalElement(RIL.WORD, RIL.SYMBOL):
                                        break
                                    else:
                                        result_it.Next(RIL.SYMBOL)
                            if result_it.IsAtFinalElement(RIL.TEXTLINE, RIL.WORD):
                                break
                            else:
                                result_it.Next(RIL.WORD)
                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    basename=ID + '.xml',
                    mimetype=MIMETYPE_PAGE,
                    content=to_xml(pcgts),
                )
