from __future__ import absolute_import
import os.path
from PIL import Image, ImageStat

from tesserocr import (
    RIL, PSM, PT,
    PyTessBaseAPI, get_languages as get_languages_)

from ocrd_utils import (
    getLogger,
    points_from_polygon,
    make_file_id,
    assert_file_grp_cardinality,
    polygon_from_x0y0x1y1,
    xywh_from_polygon,
    coordinates_for_segment,
    MIMETYPE_PAGE,
    membername
)
from ocrd_models.ocrd_page import (
    CoordsType,
    ImageRegionType,
    MathsRegionType,
    SeparatorRegionType,
    NoiseRegionType,
    TableRegionType,
    TextRegionType,
    TextLineType,
    WordType,
    GlyphType,
    TextEquivType,
    to_xml)
from ocrd_models.ocrd_page_generateds import (
    ReadingDirectionSimpleType,
    TextLineOrderSimpleType,
    ReadingOrderType,
    RegionRefType,
    RegionRefIndexedType,
    OrderedGroupType,
    OrderedGroupIndexedType,
    UnorderedGroupType,
    UnorderedGroupIndexedType,
    TextTypeSimpleType
)
from ocrd_modelfactory import page_from_file
from ocrd import Processor

from .config import TESSDATA_PREFIX, OCRD_TOOL
from .segment import polygon_for_parent, iterate_level

TOOL = 'ocrd-tesserocr-recognize'

CHOICE_THRESHOLD_NUM = 6 # maximum number of choices to query and annotate
CHOICE_THRESHOLD_CONF = 0.2 # maximum score drop from best choice to query and annotate

def get_languages(*args, **kwargs):
    """
    Wraps tesserocr.get_languages() with a fixed path parameter.
    """
    return get_languages_(*args, path=TESSDATA_PREFIX, **kwargs)

class TesserocrRecognize(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrRecognize, self).__init__(*args, **kwargs)

    def process(self):
        """Perform layout segmentation and/or text recognition with Tesseract on the workspace.
        
        Open and deserialise PAGE input files and their respective images,
        then iterate over the element hierarchy down to the requested
        ``textequiv_level`` if it exists, and if each level's respective
        ``overwrite_LEVEL`` is disabled. 
        Otherwise stop at the highest level with ``overwrite_LEVEL==True``,
        and remove any existing segmentation at that level.
        
        Set up Tesseract to recognise each segment's image (either from
        AlternativeImage or cropping the bounding box rectangle and masking
        it from the polygon outline) with the appropriate mode and ``model``.
        
        Next, iterate over the result hierarchy from the current level
        in the PAGE hierarchy down to the requested ``textequiv_level``,
        creating new segmentation at each level.
        
        Put text and confidence results into the TextEquiv at ``textequiv_level``,
        removing any existing TextEquiv.
        
        Finally, make all higher levels consistent with these text results
        by concatenation, ordering according to each level's respective
        readingDirection, textLineOrder, and ReadingOrder, and joining
        by whitespace as appropriate for each level and according to its
        Relation/join status.
        
        The special value ``none`` for ``textequiv_level`` behaves like ``word``,
        except that no actual text recognition will be performed, only layout
        analysis.
        
        In other words:
        - If ``overwrite_regions``, segment regions, else iterate existing regions.
        - If ``textequiv_level==region``, then recognize text in the region,
          annotate it, and continue with the next region. Otherwise...
        - If ``overwrite_lines``, segment lines, else iterate existing text lines.
        - If ``textequiv_level==line``, then recognize text in the text lines,
          annotate it, and continue with the next line. Otherwise...
        - If ``overwrite_words``, segment words, else iterate existing words.
        - If ``textequiv_level==word``, then recognize text in the words,
          annotate it, and continue with the next word. Otherwise...
        - If ``textequiv_level==glyph``, then recognize text in the glyphs and
          continue with the next glyph. Otherwise...
        - (i.e. ``none``) annotate no text and be done with segmentation.
        
        Thus, enabling the ``overwrite_*`` modes makes this processor behave more
        like a segmentation processor, and setting ``textequiv_level`` to ``none``
        makes it a segmentation-only processor.
        
        If ``find_tables``, then during region segmentation, also try to detect
        table blocks and add them as TableRegion, then query the page iterator
        for paragraphs and add them as TextRegion cells.
        
        If ``block_polygons``, then during region segmentation, query Tesseract
        for polygon outlines instead of bounding boxes for each region.
        (This is more precise, but due to some path representation errors does
        not always yield accurate/valid polygons.)
        
        If ``sparse_text``, then during region segmentation, attempt to find
        single-line text blocks in no particular order.
        
        Produce new output files by serialising the resulting hierarchy.
        """
        LOG = getLogger('processor.TesserocrRecognize')
        LOG.debug("TESSDATA: %s, installed Tesseract models: %s", *get_languages())

        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        maxlevel = self.parameter['textequiv_level']
        model = get_languages()[1][-1] # last installed model
        if 'model' in self.parameter:
            model = self.parameter['model']
            for sub_model in model.split('+'):
                if sub_model not in get_languages()[1]:
                    raise Exception("configured model " + sub_model + " is not installed")
        
        with PyTessBaseAPI(path=TESSDATA_PREFIX, lang=model) as tessapi:
            if self.parameter['find_tables']:
                if maxlevel == 'region':
                    raise Exception("When find_tables is enabled, textequiv_level must be at least table, because text results cannot be annotated on tables directly.")
                tessapi.SetVariable("textord_tabfind_find_tables", "1") # (default)
                # this should yield additional blocks within the table blocks
                # from the page iterator, but does not in fact (yet?):
                # (and it can run into assertion errors when the table structure
                #  does not meet certain homogeneity expectations)
                #tessapi.SetVariable("textord_tablefind_recognize_tables", "1")
            else:
                # disable table detection here, so tables will be
                # analysed as independent text/line blocks:
                tessapi.SetVariable("textord_tabfind_find_tables", "0")
            LOG.info("Using model '%s' in %s for recognition at the %s level",
                     model, get_languages()[0], maxlevel)
            if maxlevel == 'glyph':
                # populate GetChoiceIterator() with LSTM models, too:
                tessapi.SetVariable("lstm_choice_mode", "2") # aggregate symbols
                tessapi.SetVariable("lstm_choice_iterations", "15") # squeeze out more best paths
            # TODO: maybe warn/raise when illegal combinations or characters not in the model unicharset?
            if self.parameter['char_whitelist']:
                tessapi.SetVariable("tessedit_char_whitelist", self.parameter['char_whitelist'])
            if self.parameter['char_blacklist']:
                tessapi.SetVariable("tessedit_char_blacklist", self.parameter['char_blacklist'])
            if self.parameter['char_unblacklist']:
                tessapi.SetVariable("tessedit_char_unblacklist", self.parameter['char_unblacklist'])
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
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if self.parameter['dpi'] > 0:
                    dpi = self.parameter['dpi']
                    LOG.info("Page '%s' images will use %d DPI from paramter override", page_id, dpi)
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
                if self.parameter['overwrite_regions']:
                    for regiontype in [
                            'AdvertRegion',
                            'ChartRegion',
                            'ChemRegion',
                            'GraphicRegion',
                            'ImageRegion',
                            'LineDrawingRegion',
                            'MathsRegion',
                            'MusicRegion',
                            'NoiseRegion',
                            'SeparatorRegion',
                            'TableRegion',
                            'TextRegion',
                            'UnknownRegion']:
                        if getattr(page, 'get_' + regiontype)():
                            LOG.info('Removing existing %ss', regiontype)
                        getattr(page, 'set_' + regiontype)([])
                    page.set_ReadingOrder(None)
                    tessapi.SetImage(page_image) # is already cropped to Border
                    tessapi.SetPageSegMode(PSM.SPARSE_TEXT
                                           if self.parameter['sparse_text']
                                           else PSM.AUTO)
                    if maxlevel == 'none':
                        LOG.debug("Detecting regions in page '%s'", page_id)
                        tessapi.AnalyseLayout()
                    else:
                        LOG.debug("Recognizing text in page '%s'", page_id)
                        tessapi.Recognize()
                    self._process_regions_in_page(tessapi.GetIterator(), page, page_coords, dpi)
                else:
                    regions = page.get_AllRegions(classes=['Text'])
                    if not regions:
                        LOG.warning("Page '%s' contains no text regions", page_id)
                    else:
                        self._process_existing_regions(tessapi, regions, page_image, page_coords)
                
                if maxlevel != 'none':
                    page_update_higher_textequiv_levels(maxlevel, pcgts)
                
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

    def _process_regions_in_page(self, result_it, page, page_coords, dpi):
        LOG = getLogger('processor.TesserocrRecognize')
        index = 0
        ro = page.get_ReadingOrder()
        if not ro:
            ro = ReadingOrderType()
            page.set_ReadingOrder(ro)
        og = ro.get_OrderedGroup()
        if og:
            # start counting from largest existing index
            for elem in (og.get_RegionRefIndexed() +
                         og.get_OrderedGroupIndexed() +
                         og.get_UnorderedGroupIndexed()):
                if elem.index >= index:
                    index = elem.index + 1
        else:
            # new top-level group
            og = OrderedGroupType(id="reading-order")
            ro.set_OrderedGroup(og)
        # equivalent to GetComponentImages with raw_image=True,
        # (which would also give raw coordinates),
        # except we are also interested in the iterator's BlockType() here,
        # and its BlockPolygon()
        for it in iterate_level(result_it, RIL.BLOCK):
            # (padding will be passed to both BoundingBox and GetImage)
            # (actually, Tesseract honours padding only on the left and bottom,
            #  whereas right and top are increased less!)
            x0y0x1y1 = it.BoundingBox(RIL.BLOCK, padding=self.parameter['padding'])
            # sometimes these polygons are not planar, which causes
            # PIL.ImageDraw.Draw.polygon (and likely others as well)
            # to misbehave; however, PAGE coordinate semantics prohibit
            # multi-path polygons!
            # (probably a bug in Tesseract itself, cf. tesseract#2826):
            if self.parameter['block_polygons']:
                polygon = it.BlockPolygon()
            else:
                polygon = polygon_from_x0y0x1y1(x0y0x1y1)
            xywh = xywh_from_polygon(polygon)
            polygon = coordinates_for_segment(polygon, None, page_coords)
            polygon2 = polygon_for_parent(polygon, page)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            # plausibilise candidate
            if polygon2 is None:
                LOG.info('Ignoring extant region: %s', points)
                continue
            block_type = it.BlockType()
            if block_type in [
                    PT.FLOWING_TEXT,
                    PT.HEADING_TEXT,
                    PT.PULLOUT_TEXT,
                    PT.CAPTION_TEXT,
                    PT.VERTICAL_TEXT,
                    PT.INLINE_EQUATION,
                    PT.EQUATION,
                    PT.TABLE] and (
                        xywh['w'] < 20 / 300.0*(dpi or 300) or
                        xywh['h'] < 30 / 300.0*(dpi or 300)):
                LOG.info('Ignoring too small region: %s', points)
                continue
            region_image_bin = it.GetBinaryImage(RIL.BLOCK)
            if not region_image_bin.getbbox():
                LOG.info('Ignoring binary-empty region: %s', points)
                continue
            #
            # add the region reference in the reading order element
            # (will be removed again if Separator/Noise region below)
            ID = "region%04d" % index
            og.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
            #
            # region type switch
            #
            block_type = it.BlockType()
            LOG.info("Detected region '%s': %s (%s)", ID, points, membername(PT, block_type))
            if block_type in [PT.FLOWING_TEXT,
                              PT.HEADING_TEXT,
                              PT.PULLOUT_TEXT,
                              PT.CAPTION_TEXT,
                              # TABLE is contained in PTIsTextType, but
                              # it is a bad idea to create a TextRegion
                              # for it (better set `find_tables` False):
                              # PT.TABLE,
                              # will also get a 90° @orientation
                              # (but that can be overridden by deskew/OSD):
                              PT.VERTICAL_TEXT]:
                region = TextRegionType(id=ID, Coords=coords,
                                        type=TextTypeSimpleType.PARAGRAPH)
                if block_type == PT.VERTICAL_TEXT:
                    region.set_orientation(90.0)
                elif block_type == PT.HEADING_TEXT:
                    region.set_type(TextTypeSimpleType.HEADING)
                elif block_type == PT.PULLOUT_TEXT:
                    region.set_type(TextTypeSimpleType.FLOATING)
                elif block_type == PT.CAPTION_TEXT:
                    region.set_type(TextTypeSimpleType.CAPTION)
                page.add_TextRegion(region)
                if self.parameter['textequiv_level'] == 'region':
                    region.add_TextEquiv(TextEquivType(
                        Unicode=it.GetUTF8Text().rstrip("\n\f"),
                        # iterator scores are arithmetic averages, too
                        conf=it.MeanTextConf()/100.0))
                else:
                    self._process_lines_in_region(it, region, page_coords)
            elif block_type in [PT.FLOWING_IMAGE,
                                PT.HEADING_IMAGE,
                                PT.PULLOUT_IMAGE]:
                region = ImageRegionType(id=ID, Coords=coords)
                page.add_ImageRegion(region)
            elif block_type in [PT.HORZ_LINE,
                                PT.VERT_LINE]:
                region = SeparatorRegionType(id=ID, Coords=coords)
                page.add_SeparatorRegion(region)
                # undo appending in ReadingOrder
                og.set_RegionRefIndexed(og.get_RegionRefIndexed()[:-1])
            elif block_type in [PT.INLINE_EQUATION,
                                PT.EQUATION]:
                region = MathsRegionType(id=ID, Coords=coords)
                page.add_MathsRegion(region)
            elif block_type == PT.TABLE:
                # without API access to StructuredTable we cannot
                # do much for a TableRegionType (i.e. nrows, ncols,
                # coordinates of cells for recursive regions etc),
                # but this can be achieved afterwards by segment-table
                region = TableRegionType(id=ID, Coords=coords)
                page.add_TableRegion(region)
                if self.parameter['textequiv_level'] == 'region':
                    pass # impossible (see exception above)
                    # todo: TableRegionType has no TextEquiv in PAGE
                    # region.add_TextEquiv(TextEquivType(
                    #     Unicode=it.GetUTF8Text().rstrip("\n\f"),
                    #     # iterator scores are arithmetic averages, too
                    #     conf=it.MeanTextConf()/100.0))
                else:
                    self._process_cells_in_table(it, region, page_coords)
            else:
                region = NoiseRegionType(id=ID, Coords=coords)
                page.add_NoiseRegion()
                # undo appending in ReadingOrder
                og.set_RegionRefIndexed(og.get_RegionRefIndexed()[:-1])
            #
            # iterator increment
            #
            index += 1
        if (not og.get_RegionRefIndexed() and
            not og.get_OrderedGroupIndexed() and
            not og.get_UnorderedGroupIndexed()):
            # schema forbids empty OrderedGroup
            ro.set_OrderedGroup(None)
    
    def _process_cells_in_table(self, result_it, region, page_coords):
        LOG = getLogger('processor.TesserocrRecognize')
        for index, it in enumerate(iterate_level(result_it, RIL.PARA)):
            bbox = it.BoundingBox(RIL.PARA, padding=self.parameter['padding'])
            polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, page_coords)
            polygon2 = polygon_for_parent(polygon, region)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            if polygon2 is None:
                LOG.info('Ignoring extant cell: %s', points)
                continue
            ID = region.id + "_cell%04d" % index
            LOG.info("Detected cell '%s': %s", ID, points)
            cell = TextRegionType(id=ID, Coords=coords)
            region.add_TextRegion(cell)
            if self.parameter['textequiv_level'] == 'table':
                cell.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=it.MeanTextConf()/100.0))
            else:
                self._process_lines_in_region(it, cell, page_coords)
        
    def _process_lines_in_region(self, result_it, region, page_coords):
        LOG = getLogger('processor.TesserocrRecognize')
        if self.parameter['sparse_text']:
            it = result_it
            region.set_type(TextTypeSimpleType.OTHER)
            line = TextLineType(id=region.id + '_line',
                                Coords=region.get_Coords())
            region.add_TextLine(line)
            if self.parameter['textequiv_level'] == 'line':
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=it.MeanTextConf()/100.0))
            else:
                self._process_words_in_line(it, line, page_coords)
            return
        for index, it in enumerate(iterate_level(result_it, RIL.TEXTLINE)):
            bbox = it.BoundingBox(RIL.TEXTLINE, padding=self.parameter['padding'])
            polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, page_coords)
            polygon2 = polygon_for_parent(polygon, region)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            if polygon2 is None:
                LOG.info('Ignoring extant line: %s', points)
                continue
            ID = region.id + "_line%04d" % index
            LOG.info("Detected line '%s': %s", ID, points)
            line = TextLineType(id=ID, Coords=coords)
            region.add_TextLine(line)
            if self.parameter['textequiv_level'] == 'line':
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=it.MeanTextConf()/100.0))
            else:
                self._process_words_in_line(it, line, page_coords)
    
    def _process_words_in_line(self, result_it, line, coords):
        LOG = getLogger('processor.TesserocrRecognize')
        for index, it in enumerate(iterate_level(result_it, RIL.WORD)):
            bbox = it.BoundingBox(RIL.WORD, padding=self.parameter['padding'])
            polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, coords)
            polygon2 = polygon_for_parent(polygon, line)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            if polygon2 is None:
                LOG.info('Ignoring extant word: %s', points)
                continue
            ID = line.id + "_word%04d" % index
            LOG.info("Detected word '%s': %s", ID, points)
            word = WordType(id=ID, Coords=CoordsType(points=points))
            line.add_Word(word)
            if self.parameter['textequiv_level'] in ['word', 'glyph']:
                word.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text(RIL.WORD),
                    # iterator scores are arithmetic averages, too
                    conf=it.Confidence(RIL.WORD)/100.0))
            if self.parameter['textequiv_level'] == 'glyph':
                self._process_glyphs_in_word(it, word, coords)
    
    def _process_glyphs_in_word(self, result_it, word, coords):
        LOG = getLogger('processor.TesserocrRecognize')
        for index, it in enumerate(iterate_level(result_it, RIL.SYMBOL)):
            bbox = it.BoundingBox(RIL.SYMBOL, padding=self.parameter['padding'])
            polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, coords)
            polygon2 = polygon_for_parent(polygon, word)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            if polygon2 is None:
                LOG.info('Ignoring extant glyph: %s', points)
                continue
            ID = word.id + '_glyph%04d' % index
            LOG.debug("Detected glyph '%s': %s", ID, points)
            glyph = GlyphType(id=ID, Coords=CoordsType(points))
            word.add_Glyph(glyph)
            # glyph_text = it.GetUTF8Text(RIL.SYMBOL) # equals first choice?
            glyph_conf = it.Confidence(RIL.SYMBOL)/100 # equals first choice?
            #LOG.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
            choice_it = it.GetChoiceIterator()
            for choice_no, choice in enumerate(choice_it):
                alternative_text = choice.GetUTF8Text()
                alternative_conf = choice.Confidence()/100
                #LOG.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                    choice_no > CHOICE_THRESHOLD_NUM):
                    break
                # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                glyph.add_TextEquiv(TextEquivType(
                    index=choice_no,
                    Unicode=alternative_text,
                    conf=alternative_conf))
    
    def _process_existing_regions(self, tessapi, regions, page_image, page_coords):
        LOG = getLogger('processor.TesserocrRecognize')
        for region in regions:
            region_image, region_coords = self.workspace.image_from_segment(
                region, page_image, page_coords)
            if self.parameter['padding']:
                tessapi.SetImage(pad_image(region_image, self.parameter['padding']))
            else:
                tessapi.SetImage(region_image)
            tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
            if self.parameter['textequiv_level'] == 'region':
                #if region.get_primaryScript() not in tessapi.GetLoadedLanguages()...
                LOG.debug("Recognizing text in region '%s'", region.id)
                region.set_TextLine([])
                if region.get_TextEquiv():
                    LOG.warning("Region '%s' already contained text results", region.id)
                    region.set_TextEquiv([])
                # todo: consider SetParagraphSeparator
                region.add_TextEquiv(TextEquivType(
                    Unicode=tessapi.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=tessapi.MeanTextConf()/100.0))
                continue # next region (to avoid indentation below)
            ## line, word, or glyph level:
            textlines = region.get_TextLine()
            if self.parameter['overwrite_lines']:
                if textlines:
                    LOG.info('Removing existing text lines')
                region.set_TextLine([])
                if self.parameter['textequiv_level'] == 'none':
                    LOG.debug("Detecting lines in region '%s'", region.id)
                    tessapi.AnalyseLayout()
                else:
                    LOG.debug("Recognizing text in region '%s'", region.id)
                    tessapi.Recognize()
                self._process_lines_in_region(tessapi.GetIterator(), region, region_coords)
            else:
                if not textlines:
                    LOG.warning("Region '%s' contains no text lines", region.id)
                else:
                    self._process_existing_lines(tessapi, textlines, region_image, region_coords)

    def _process_existing_lines(self, tessapi, textlines, region_image, region_coords):
        LOG = getLogger('processor.TesserocrRecognize')
        for line in textlines:
            line_image, line_coords = self.workspace.image_from_segment(
                line, region_image, region_coords)
            if self.parameter['padding']:
                tessapi.SetImage(pad_image(line_image, self.parameter['padding']))
            else:
                tessapi.SetImage(line_image)
            if self.parameter['raw_lines']:
                tessapi.SetPageSegMode(PSM.RAW_LINE)
            else:
                tessapi.SetPageSegMode(PSM.SINGLE_LINE)
            #if line.get_primaryScript() not in tessapi.GetLoadedLanguages()...
            if self.parameter['textequiv_level'] == 'line':
                LOG.debug("Recognizing text in line '%s'", line.id)
                line.set_Word([])
                if line.get_TextEquiv():
                    LOG.warning("Line '%s' already contained text results", line.id)
                    line.set_TextEquiv([])
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(
                    Unicode=tessapi.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=tessapi.MeanTextConf()/100.0))
                continue # next line (to avoid indentation below)
            ## word, or glyph level:
            words = line.get_Word()
            if self.parameter['overwrite_words']:
                if words:
                    LOG.info('Removing existing words')
                line.set_Word([])
                if self.parameter['textequiv_level'] == 'none':
                    LOG.debug("Detecting words in line '%s'", line.id)
                    tessapi.AnalyseLayout()
                else:
                    LOG.debug("Recognizing text in line '%s'", line.id)
                    tessapi.Recognize()
                    ## internal word and glyph layout:
                self._process_words_in_line(tessapi.GetIterator(), line, line_coords)
            else:
                if words:
                    ## external word layout:
                    LOG.warning("Line '%s' contains words already, recognition might be suboptimal", line.id)
                    self._process_existing_words(tessapi, words, line_image, line_coords)

    def _process_existing_words(self, tessapi, words, line_image, line_coords):
        LOG = getLogger('processor.TesserocrRecognize')
        for word in words:
            word_image, word_coords = self.workspace.image_from_segment(
                word, line_image, line_coords)
            if self.parameter['padding']:
                tessapi.SetImage(pad_image(word_image, self.parameter['padding']))
            else:
                tessapi.SetImage(word_image)
            tessapi.SetPageSegMode(PSM.SINGLE_WORD)
            if self.parameter['textequiv_level'] == 'word':
                LOG.debug("Recognizing text in word '%s'", word.id)
                word.set_Glyph([])
                if word.get_TextEquiv():
                    LOG.warning("Word '%s' already contained text results", word.id)
                    word.set_TextEquiv([])
                word_conf = tessapi.AllWordConfidences()
                word.add_TextEquiv(TextEquivType(
                    Unicode=tessapi.GetUTF8Text().rstrip("\n\f"),
                    conf=word_conf[0]/100.0 if word_conf else 0.0))
                continue # next word (to avoid indentation below)
            if self.parameter['textequiv_level'] == 'none':
                continue
            ## glyph level:
            glyphs = word.get_Glyph()
            if glyphs:
                ## external glyph layout:
                LOG.warning("Word '%s' contains glyphs already, recognition might be suboptimal", word.id)
                self._process_existing_glyphs(tessapi, glyphs, word_image, word_coords)
            else:
                ## internal glyph layout:
                LOG.debug("Recognizing text in word '%s'", word.id)
                tessapi.Recognize()
                self._process_glyphs_in_word(tessapi.GetIterator(), word, word_coords)

    def _process_existing_glyphs(self, tessapi, glyphs, word_image, word_xywh):
        LOG = getLogger('processor.TesserocrRecognize')
        for glyph in glyphs:
            glyph_image, _ = self.workspace.image_from_segment(
                glyph, word_image, word_xywh)
            if self.parameter['padding']:
                tessapi.SetImage(pad_image(glyph_image, self.parameter['padding']))
            else:
                tessapi.SetImage(glyph_image)
            tessapi.SetPageSegMode(PSM.SINGLE_CHAR)
            LOG.debug("Recognizing text in glyph '%s'", glyph.id)
            if glyph.get_TextEquiv():
                LOG.warning("Glyph '%s' already contained text results", glyph.id)
                glyph.set_TextEquiv([])
            #glyph_text = tessapi.GetUTF8Text().rstrip("\n\f")
            glyph_conf = tessapi.AllWordConfidences()
            glyph_conf = glyph_conf[0]/100.0 if glyph_conf else 1.0
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
                glyph.add_TextEquiv(TextEquivType(
                    index=choice_no, Unicode=alternative_text, conf=alternative_conf))

def page_element_unicode0(element):
    """Get Unicode string of the first text result."""
    if element.get_TextEquiv():
        return element.get_TextEquiv()[0].Unicode
    else:
        return ''

def page_element_conf0(element):
    """Get confidence (as float value) of the first text result."""
    if element.get_TextEquiv():
        # generateDS does not convert simpleType for attributes (yet?)
        return float(element.get_TextEquiv()[0].conf or "1.0")
    return 1.0

def page_get_reading_order(ro, rogroup):
    """Add all elements from the given reading order group to the given dictionary.
    
    Given a dict ``ro`` from layout element IDs to ReadingOrder element objects,
    and an object ``rogroup`` with additional ReadingOrder element objects,
    add all references to the dict, traversing the group recursively.
    """
    regionrefs = list()
    if isinstance(rogroup, (OrderedGroupType, OrderedGroupIndexedType)):
        regionrefs = (rogroup.get_RegionRefIndexed() +
                      rogroup.get_OrderedGroupIndexed() +
                      rogroup.get_UnorderedGroupIndexed())
    if isinstance(rogroup, (UnorderedGroupType, UnorderedGroupIndexedType)):
        regionrefs = (rogroup.get_RegionRef() +
                      rogroup.get_OrderedGroup() +
                      rogroup.get_UnorderedGroup())
    for elem in regionrefs:
        ro[elem.get_regionRef()] = elem
        if not isinstance(elem, (RegionRefType, RegionRefIndexedType)):
            page_get_reading_order(ro, elem)
        
def page_update_higher_textequiv_levels(level, pcgts):
    """Update the TextEquivs of all PAGE-XML hierarchy levels above ``level`` for consistency.
    
    Starting with the hierarchy level chosen for processing,
    join all first TextEquiv.Unicode (by the rules governing the respective level)
    into TextEquiv.Unicode of the next higher level, replacing them.
    
    When two successive elements appear in a ``Relation`` of type ``join``,
    then join them directly (without their respective white space).
    
    Likewise, average all first TextEquiv.conf into TextEquiv.conf of the next higher level.
    
    In the process, traverse the words and lines in their respective ``readingDirection``,
    the (text) regions which contain lines in their respective ``textLineOrder``, and
    the (text) regions which contain text regions in their ``ReadingOrder``
    (if they appear there as an ``OrderedGroup``).
    Where no direction/order can be found, use XML ordering.
    
    Follow regions recursively, but make sure to traverse them in a depth-first strategy.
    """
    page = pcgts.get_Page()
    relations = page.get_Relations() # get RelationsType
    if relations:
        relations = relations.get_Relation() # get list of RelationType
    else:
        relations = []
    joins = list() # 
    for relation in relations:
        if relation.get_type() == 'join': # ignore 'link' type here
            joins.append((relation.get_SourceRegionRef().get_regionRef(),
                          relation.get_TargetRegionRef().get_regionRef()))
    reading_order = dict()
    ro = page.get_ReadingOrder()
    if ro:
        page_get_reading_order(reading_order, ro.get_OrderedGroup() or ro.get_UnorderedGroup())
    if level != 'region':
        for region in page.get_AllRegions(classes=['Text']):
            # order is important here, because regions can be recursive,
            # and we want to concatenate by depth first;
            # typical recursion structures would be:
            #  - TextRegion/@type=paragraph inside TextRegion
            #  - TextRegion/@type=drop-capital followed by TextRegion/@type=paragraph inside TextRegion
            #  - any region (including TableRegion or TextRegion) inside a TextRegion/@type=footnote
            #  - TextRegion inside TableRegion
            subregions = region.get_TextRegion()
            if subregions: # already visited in earlier iterations
                # do we have a reading order for these?
                # TODO: what if at least some of the subregions are in reading_order?
                if (all(subregion.id in reading_order for subregion in subregions) and
                    isinstance(reading_order[subregions[0].id], # all have .index?
                               (OrderedGroupType, OrderedGroupIndexedType))):
                    subregions = sorted(subregions, key=lambda subregion:
                                        reading_order[subregion.id].index)
                region_unicode = page_element_unicode0(subregions[0])
                for subregion, next_subregion in zip(subregions, subregions[1:]):
                    if (subregion.id, next_subregion.id) not in joins:
                        region_unicode += '\n' # or '\f'?
                    region_unicode += page_element_unicode0(next_subregion)
                region_conf = sum(page_element_conf0(subregion) for subregion in subregions)
                region_conf /= len(subregions)
            else: # TODO: what if a TextRegion has both TextLine and TextRegion children?
                lines = region.get_TextLine()
                if ((region.get_textLineOrder() or
                     page.get_textLineOrder()) ==
                    TextLineOrderSimpleType.BOTTOMTOTOP):
                    lines = list(reversed(lines))
                if level != 'line':
                    for line in lines:
                        words = line.get_Word()
                        if ((line.get_readingDirection() or
                             region.get_readingDirection() or
                             page.get_readingDirection()) ==
                            ReadingDirectionSimpleType.RIGHTTOLEFT):
                            words = list(reversed(words))
                        if level != 'word':
                            for word in words:
                                glyphs = word.get_Glyph()
                                if ((word.get_readingDirection() or
                                     line.get_readingDirection() or
                                     region.get_readingDirection() or
                                     page.get_readingDirection()) ==
                                    ReadingDirectionSimpleType.RIGHTTOLEFT):
                                    glyphs = list(reversed(glyphs))
                                word_unicode = ''.join(page_element_unicode0(glyph) for glyph in glyphs)
                                word_conf = sum(page_element_conf0(glyph) for glyph in glyphs)
                                if glyphs:
                                    word_conf /= len(glyphs)
                                word.set_TextEquiv( # replace old, if any
                                    [TextEquivType(Unicode=word_unicode, conf=word_conf)])
                        line_unicode = ' '.join(page_element_unicode0(word) for word in words)
                        line_conf = sum(page_element_conf0(word) for word in words)
                        if words:
                            line_conf /= len(words)
                        line.set_TextEquiv( # replace old, if any
                            [TextEquivType(Unicode=line_unicode, conf=line_conf)])
                region_unicode = ''
                region_conf = 0
                if lines:
                    region_unicode = page_element_unicode0(lines[0])
                    for line, next_line in zip(lines, lines[1:]):
                        words = line.get_Word()
                        next_words = next_line.get_Word()
                        if not(words and next_words and (words[-1].id, next_words[0].id) in joins):
                            region_unicode += '\n'
                        region_unicode += page_element_unicode0(next_line)
                    region_conf = sum(page_element_conf0(line) for line in lines)
                    region_conf /= len(lines)
            region.set_TextEquiv( # replace old, if any
                [TextEquivType(Unicode=region_unicode, conf=region_conf)])

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
