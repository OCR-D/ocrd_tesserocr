from __future__ import absolute_import
import os.path
import math
from PIL import Image, ImageStat
import numpy as np
from shapely.geometry import Polygon, asPolygon
from shapely.ops import unary_union

from tesserocr import (
    RIL, PSM, PT, OEM,
    Orientation,
    WritingDirection,
    TextlineOrder,
    tesseract_version,
    PyTessBaseAPI, get_languages as get_languages_)

from ocrd_utils import (
    getLogger,
    make_file_id,
    assert_file_grp_cardinality,
    shift_coordinates,
    coordinates_for_segment,
    polygon_from_x0y0x1y1,
    polygon_from_points,
    points_from_polygon,
    xywh_from_polygon,
    MIMETYPE_PAGE,
    membername
)
from ocrd_models.ocrd_page import (
    ReadingOrderType,
    RegionRefType,
    RegionRefIndexedType,
    OrderedGroupType,
    OrderedGroupIndexedType,
    UnorderedGroupType,
    UnorderedGroupIndexedType,
    PageType,
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
    AlternativeImageType,
    to_xml)
from ocrd_models.ocrd_page_generateds import (
    ReadingDirectionSimpleType,
    TextLineOrderSimpleType,
    TextTypeSimpleType
)
from ocrd_modelfactory import page_from_file
from ocrd import Processor

from .config import get_tessdata_path, OCRD_TOOL

TOOL = 'ocrd-tesserocr-recognize'

CHOICE_THRESHOLD_NUM = 10 # maximum number of choices to query and annotate
CHOICE_THRESHOLD_CONF = 1 # maximum score drop from best choice to query and annotate
# (ChoiceIterator usually rounds to 0.0 for non-best, so this better be maximum)

def get_languages(*args, **kwargs):
    """
    Wraps tesserocr.get_languages() with a fixed path parameter.
    """
    return get_languages_(*args, path=get_tessdata_path(), **kwargs)

# monkey-patch the tesserocr base class so have at least some state
class TessBaseAPI(PyTessBaseAPI):
    parameters = {}
    psm = PSM.AUTO
    image = None
    path = ''
    lang = ''
    oem = OEM.DEFAULT

    def __repr__(self):
        return str({'parameters': self.parameters,
                    'psm': self.psm,
                    'image': self.image,
                    'path': self.path,
                    'lang': self.lang,
                    'oem': self.oem})

    def InitFull(self, path=None, lang=None, oem=None, psm=None, variables=None):
        self.path = path or self.path
        self.lang = lang or self.lang
        self.oem = oem or self.oem
        self.parameters = variables or self.parameters
        super().InitFull(path=self.path, lang=self.lang, oem=self.oem, variables=self.parameters)

    def SetVariable(self, name, val):
        self.parameters[name] = val
        return super().SetVariable(name, val)

    def SetPageSegMode(self, psm):
        self.psm = psm
        super().SetPageSegMode(psm)

    def Reset(self, path=None, lang=None, oem=None, psm=None, parameters=None):
        self.Clear()
        self.InitFull(path=path, lang=lang, oem=oem, variables=parameters)
        self.SetPageSegMode(psm or self.psm)

    def __enter__(self):
        self.original_path = self.path
        self.original_lang = self.lang
        self.original_oem = self.oem
        self.original_parameters = self.parameters.copy()
        self.original_psm = self.psm
        return self

    def __exit__(self, exc_type, exc_val, exc_trace):
        self.path = self.original_path
        self.lang = self.original_lang
        self.oem = self.original_oem
        self.parameters = self.original_parameters
        self.psm = self.original_psm
        return None

class TesserocrRecognize(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version'] + ' (' + tesseract_version().split('\n')[0] + ')'
        super(TesserocrRecognize, self).__init__(*args, **kwargs)
        
        if hasattr(self, 'workspace'):
            self.logger = getLogger('processor.TesserocrRecognize')

    def process(self):
        """Perform layout segmentation and/or text recognition with Tesseract on the workspace.
        
        Open and deserialise PAGE input files and their respective images,
        then iterate over the element hierarchy down to the requested
        ``textequiv_level`` if it exists and if ``segmentation_level``
        is lower (i.e. more granular) or ``none``.
        
        Otherwise stop before (i.e. above) ``segmentation_level``. If any
        segmentation exist at that level already, and ``overwrite_segments``
        is false, then descend into these segments, else remove them.
        
        Set up Tesseract to recognise each segment's image (either from
        AlternativeImage or cropping the bounding box rectangle and masking
        it from the polygon outline) with the appropriate segmentation mode
        and ``model``. (If no ``model`` is given, only layout analysis will
        be performed.)
        
        Next, if there still is a gap between the current level in the PAGE hierarchy
        and the requested ``textequiv_level``, then iterate down the result hierarchy,
        adding new segments at each level (as well as reading order references,
        text line order, reading direction and orientation at the region/table level).
        
        Then, at ``textequiv_level``, remove any existing TextEquiv, unless
        ``overwrite_text`` is false, and add text and confidence results, unless
        ``model`` is empty.
        
        The special value ``textequiv_level=none`` behaves like ``glyph``,
        except that no actual text recognition will be performed, only
        layout analysis (so no ``model`` is needed, and new segmentation
        is created down to the glyph level).
        
        The special value ``segmentation_level=none`` likewise is lowest,
        i.e. no actual layout analysis will be performed, only
        text recognition (so existing segmentation is needed down to
        ``textequiv_level``).
        
        Finally, make all higher levels consistent with these text results
        by concatenation, ordering according to each level's respective
        readingDirection, textLineOrder, and ReadingOrder, and joining
        by whitespace as appropriate for each level and according to its
        Relation/join status.
        
        In other words:
        - If ``segmentation_level=region``, then segment the page into regions
          (unless ``overwrite_segments=false``), else iterate existing regions.
        - If ``textequiv_level=region``, then unless ``model`` is empty,
          recognize text in the region and annotate it. Regardless, continue
          with the next region. Otherwise...
        - If ``segmentation_level=cell`` or higher,
          then segment table regions into text regions (i.e. cells)
          (unless ``overwrite_segments=false``), else iterate existing cells.
        - If ``textequiv_level=cell``, then unless ``model`` is empty,
          recognize text in the cell and annotate it. Regardless, continue
          with the next cell. Otherwise...
        - If ``segmentation_level=line`` or higher,
          then segment text regions into text lines
          (unless ``overwrite_segments=false``), else iterate existing text lines.
        - If ``textequiv_level=line``, then unless ``model`` is empty,
          recognize text in the text lines and annotate it. Regardless, continue
          with the next line. Otherwise...
        - If ``segmentation_level=word`` or higher,
          then segment text lines into words
          (unless ``overwrite_segments=false``), else iterate existing words.
        - If ``textequiv_level=word``, then unless ``model`` is empty,
          recognize text in the words and annotate it. Regardless, continue
          with the next word. Otherwise...
        - If ``segmentation_level=glyph`` or higher,
          then segment words into glyphs
          (unless ``overwrite_segments=false``), else iterate existing glyphs.
        - If ``textequiv_level=glyph``, then unless ``model`` is empty,
          recognize text in the glyphs and annotate it. Regardless, continue
          with the next glyph. Otherwise...
        - (i.e. ``none``) annotate no text and be done.
        
        Note that ``cell`` is an _optional_ level that is only relevant for
        table regions, not text or other regions. 
        Also, when segmenting tables in the same run that detects them
        (via ``segmentation_level=region`` and ``find_tables``), cells will
        just be 'paragraphs'. In contrast, when segmenting tables that already exist
        (via ``segmentation_level=cell``), cells will be detected in ``sparse_text``
        mode, i.e. as single-line text regions.
        
        Thus, ``segmentation_level`` is the entry point level for layout analysis,
        and setting it to ``none`` makes this processor behave as recognition-only.
        Whereas ``textequiv_level`` selects the exit point level for segmentation,
        and setting it to ``none`` makes this processor behave as segmentation-only,
        as does omitting ``model``.
        
        All segments above ``segmentation_level`` must already exist, and
        no segments below ``textequiv_level`` will be newly created.
        
        If ``find_tables``, then during region segmentation, also try to detect
        table blocks and add them as TableRegion, then query the page iterator
        for paragraphs and add them as TextRegion cells.
        
        If ``block_polygons``, then during region segmentation, query Tesseract
        for polygon outlines instead of bounding boxes for each region.
        (This is more precise, but due to some path representation errors does
        not always yield accurate/valid polygons.)
        
        If ``shrink_polygons``, then during segmentation (on any level), query Tesseract
        for all symbols/glyphs of each segment and calculate the convex hull for them.
        Annotate the resulting polygon instead of the coarse bounding box.
        (This is more precise and helps avoid overlaps between neighbours, especially
        when not segmenting all levels at once.)
        
        If ``sparse_text``, then during region segmentation, attempt to find
        single-line text blocks in no particular order (Tesseract's page segmentation
        mode ``SPARSE_TEXT``).
        
        If ``tesseract_parameters`` is given, setup each of its key-value pairs as
        run-time parameters in Tesseract.
        
        Finally, produce new output files by serialising the resulting hierarchy.
        """
        self.logger.debug("TESSDATA: %s, installed Tesseract models: %s", *get_languages())

        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        inlevel = self.parameter['segmentation_level']
        outlevel = self.parameter['textequiv_level']
        segment_only = outlevel == 'none' or not self.parameter.get('model', '')
        
        model = "eng"
        self.languages = get_languages()[1]
        if 'model' in self.parameter:
            model = self.parameter['model']
            for sub_model in model.split('+'):
                if sub_model.endswith('.traineddata'):
                    self.logger.warning("Model '%s' has a  .traineddata extension, removing. Please use model names without .traineddata extension" % sub_model)
                    sub_model = sub_model.replace('.traineddata', '')
                if sub_model not in get_languages()[1]:
                    raise Exception("configured model " + sub_model + " is not installed")
            self.logger.info("Using model '%s' in %s for recognition at the %s level",
                             model, get_languages()[0], outlevel)
        
        with TessBaseAPI(init=False) as tessapi:
            # Set init-time parameters
            # self.SetVariable("debug_file", "") # show debug output (default: /dev/null)
            if outlevel == 'glyph':
                # populate GetChoiceIterator() with LSTM models, too:
                tessapi.SetVariable("lstm_choice_mode", "2") # aggregate symbols
                tessapi.SetVariable("lstm_choice_iterations", "15") # squeeze out more best paths
            tessapi.SetVariable("pageseg_apply_music_mask", "1" if self.parameter['find_staves'] else "0")
            # TODO: maybe warn/raise when illegal combinations or characters not in the model unicharset?
            if self.parameter['char_whitelist']:
                tessapi.SetVariable("tessedit_char_whitelist", self.parameter['char_whitelist'])
            if self.parameter['char_blacklist']:
                tessapi.SetVariable("tessedit_char_blacklist", self.parameter['char_blacklist'])
            if self.parameter['char_unblacklist']:
                tessapi.SetVariable("tessedit_char_unblacklist", self.parameter['char_unblacklist'])
            # todo: determine relevancy of these variables:
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
            tesseract_params = self.parameter['tesseract_parameters']
            for variable in tesseract_params:
                tessapi.SetVariable(variable, tesseract_params[variable])
            # Initialize Tesseract (loading model)
            tessapi.InitFull(path=get_tessdata_path(),
                             lang=model,
                             oem=getattr(OEM, self.parameter['oem']))
            # Iterate input files
            for (n, input_file) in enumerate(self.input_files):
                file_id = make_file_id(input_file, self.output_file_grp)
                page_id = input_file.pageId or input_file.ID
                self.logger.info("INPUT FILE %i / %s", n, page_id)
                pcgts, pcgts_tree, pcgts_mapping, pcgts_invmap = page_from_file(self.workspace.download_file(input_file),
                                                                                with_tree=True)
                pcgts.set_pcGtsId(file_id)
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id)
                if self.parameter['dpi'] > 0:
                    dpi = self.parameter['dpi']
                    self.logger.info("Page '%s' images will use %d DPI from parameter override",
                                     page_id, dpi)
                elif page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
                    self.logger.info("Page '%s' images will use %d DPI from image meta-data",
                                     page_id, dpi)
                else:
                    dpi = 0
                    self.logger.info("Page '%s' images will use DPI estimated from segmentation",
                                     page_id)
                if dpi:
                    tessapi.SetVariable('user_defined_dpi', str(dpi))
                
                self.logger.info("Processing page '%s'", page_id)
                # FIXME: We should somehow _mask_ existing regions in order to annotate incrementally (not redundantly).
                #        Currently segmentation_level=region also means removing regions,
                #        but we could have an independent setting for that, and attempt
                #        to detect regions only where nothing exists yet (by clipping to
                #        background before, or by removing clashing predictions after
                #        detection).
                regions = page.get_AllRegions(classes=['Text'])
                if inlevel == 'region' and (
                        not regions or self.parameter['overwrite_segments']):
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
                            self.logger.info('Removing existing %ss on page %s', regiontype, page_id)
                        getattr(page, 'set_' + regiontype)([])
                    page.set_ReadingOrder(None)
                    # prepare Tesseract
                    if self.parameter['find_tables']:
                        if outlevel == 'region' and self.parameter.get('model', ''):
                            raise Exception("When segmentation_level is region and find_tables is enabled, textequiv_level must be at least cell, because text results cannot be annotated on tables directly.")
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
                    tessapi.SetImage(page_image) # is already cropped to Border
                    tessapi.SetPageSegMode(PSM.SPARSE_TEXT
                                           if self.parameter['sparse_text']
                                           else PSM.AUTO)
                    if segment_only:
                        self.logger.debug("Detecting regions in page '%s'", page_id)
                        tessapi.AnalyseLayout()
                    else:
                        self._reinit(tessapi, page, pcgts_mapping)
                        self.logger.debug("Recognizing text in page '%s'", page_id)
                        tessapi.Recognize()
                    page_image_bin = tessapi.GetThresholdedImage()
                    file_path = self.workspace.save_image_file(
                        page_image_bin, file_id + '.IMG-BIN',
                        page_id=page_id,
                        file_grp=self.output_file_grp)
                    # update PAGE (reference the image file):
                    page.add_AlternativeImage(AlternativeImageType(
                        filename=file_path, comments=page_coords['features'] + ',binarized,clipped'))
                    self._process_regions_in_page(tessapi.GetIterator(), page, page_coords, pcgts_mapping, dpi)
                elif inlevel == 'cell':
                    # Tables are obligatorily recursive regions;
                    # they might have existing text regions (cells),
                    # which will be processed in the next branch
                    # (because the iterator is recursive to depth),
                    # or be empty. This is independent of whether
                    # or not they should be segmented into cells.
                    if outlevel == 'region':
                        raise Exception("When segmentation_level is cell, textequiv_level must be at least cell too, because text results cannot be annotated on tables directly.")
                    # disable table detection here, so tables will be
                    # analysed as independent text/line blocks:
                    tessapi.SetVariable("textord_tabfind_find_tables", "0")
                    tables = page.get_AllRegions(classes=['Table'])
                    if not tables:
                        self.logger.warning("Page '%s' contains no table regions (but segmentation is off)",
                                            page_id)
                    else:
                        self._process_existing_tables(tessapi, tables, page, page_image, page_coords, pcgts_mapping)
                elif regions:
                    self._process_existing_regions(tessapi, regions, page_image, page_coords, pcgts_mapping)
                else:
                    self.logger.warning("Page '%s' contains no text regions (but segmentation is off)",
                                            page_id)
                
                # post-processing
                # bottom-up text concatenation
                if outlevel != 'none' and self.parameter.get('model', ''):
                    page_update_higher_textequiv_levels(outlevel, pcgts, self.parameter['overwrite_text'])
                # bottom-up polygonal outline projection
                # if inlevel != 'none' and self.parameter['shrink_polygons']:
                #     page_shrink_higher_coordinate_levels(inlevel, outlevel, pcgts)
                
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_regions_in_page(self, result_it, page, page_coords, mapping, dpi):
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
        for i, it in enumerate(iterate_level(result_it, RIL.BLOCK)):
            # (padding will be passed to both BoundingBox and GetImage)
            # (actually, Tesseract honours padding only on the left and bottom,
            #  whereas right and top are increased less!)
            # TODO: output padding can create overlap between neighbours; at least find polygonal difference
            bbox = it.BoundingBox(RIL.BLOCK, padding=self.parameter['padding'])
            # sometimes these polygons are not planar, which causes
            # PIL.ImageDraw.Draw.polygon (and likely others as well)
            # to misbehave; however, PAGE coordinate semantics prohibit
            # multi-path polygons!
            # (probably a bug in Tesseract itself, cf. tesseract#2826):
            if self.parameter['block_polygons']:
                polygon = it.BlockPolygon()
            elif self.parameter['shrink_polygons'] and not it.Empty(RIL.SYMBOL):
                polygon = join_polygons([polygon_from_x0y0x1y1(
                    symbol.BoundingBox(RIL.SYMBOL, padding=self.parameter['padding']))
                                         for symbol in iterate_level(it, RIL.SYMBOL, parent=RIL.BLOCK)])
                # simulate a RestartBlock(), not defined by Tesseract:
                it.Begin()
                for j, it in enumerate(iterate_level(it, RIL.BLOCK)):
                    if i == j:
                        break
            else:
                polygon = polygon_from_x0y0x1y1(bbox)
            xywh = xywh_from_polygon(polygon)
            polygon = coordinates_for_segment(polygon, None, page_coords)
            polygon2 = polygon_for_parent(polygon, page)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            # plausibilise candidate
            if polygon2 is None:
                self.logger.info('Ignoring extant region: %s', points)
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
                        xywh['h'] < 10 / 300.0*(dpi or 300)):
                self.logger.info('Ignoring too small region: %s', points)
                continue
            region_image_bin = it.GetBinaryImage(RIL.BLOCK)
            if not region_image_bin or not region_image_bin.getbbox():
                self.logger.info('Ignoring binary-empty region: %s', points)
                continue
            #
            # keep and annotate new region
            ID = "region%04d" % index
            #
            # region type switch
            block_type = it.BlockType()
            self.logger.info("Detected region '%s': %s (%s)",
                             ID, points, membername(PT, block_type))
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
                og.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
                if self.parameter['textequiv_level'] not in ['region', 'cell']:
                    self._process_lines_in_region(it, region, page_coords, mapping)
                elif self.parameter.get('model', ''):
                    region.add_TextEquiv(TextEquivType(
                        Unicode=it.GetUTF8Text(RIL.BLOCK).rstrip("\n\f"),
                        # iterator scores are arithmetic averages, too
                        conf=it.Confidence(RIL.BLOCK)/100.0))
            elif block_type in [PT.FLOWING_IMAGE,
                                PT.HEADING_IMAGE,
                                PT.PULLOUT_IMAGE]:
                region = ImageRegionType(id=ID, Coords=coords)
                page.add_ImageRegion(region)
                og.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
            elif block_type in [PT.HORZ_LINE,
                                PT.VERT_LINE]:
                region = SeparatorRegionType(id=ID, Coords=coords)
                page.add_SeparatorRegion(region)
            elif block_type in [PT.INLINE_EQUATION,
                                PT.EQUATION]:
                region = MathsRegionType(id=ID, Coords=coords)
                page.add_MathsRegion(region)
                og.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
            elif block_type == PT.TABLE:
                # without API access to StructuredTable we cannot
                # do much for a TableRegionType (i.e. nrows, ncols,
                # coordinates of cells for recursive regions etc),
                # but this can be achieved afterwards by segment-table
                region = TableRegionType(id=ID, Coords=coords)
                page.add_TableRegion(region)
                rogroup = OrderedGroupIndexedType(id=ID + '_order', regionRef=ID, index=index)
                og.add_OrderedGroupIndexed(rogroup)
                if self.parameter['textequiv_level'] == 'region':
                    pass # impossible (see exception above)
                    # todo: TableRegionType has no TextEquiv in PAGE
                    # region.add_TextEquiv(TextEquivType(
                    #     Unicode=it.GetUTF8Text(RIL.BLOCK).rstrip("\n\f"),
                    #     # iterator scores are arithmetic averages, too
                    #     conf=it.Confidence(RIL.BLOCK)/100.0))
                else:
                    self._process_cells_in_table(it, region, rogroup, page_coords, mapping)
            else:
                region = NoiseRegionType(id=ID, Coords=coords)
                page.add_NoiseRegion()
            # 
            # add orientation
            if isinstance(region, (TextRegionType, TableRegionType,
                                   ImageRegionType, MathsRegionType)):
                self._add_orientation(it, region, page_coords)
            #
            # iterator increment
            #
            index += 1
        if (not og.get_RegionRefIndexed() and
            not og.get_OrderedGroupIndexed() and
            not og.get_UnorderedGroupIndexed()):
            # schema forbids empty OrderedGroup
            ro.set_OrderedGroup(None)
    
    def _process_cells_in_table(self, result_it, region, rogroup, page_coords, mapping):
        if self.parameter['segmentation_level'] == 'cell':
            ril = RIL.BLOCK # for sparse_text mode
        else:
            ril = RIL.PARA # for "cells" in PT.TABLE block
        for index, it in enumerate(iterate_level(result_it, ril)):
            bbox = it.BoundingBox(ril, padding=self.parameter['padding'])
            if self.parameter['shrink_polygons'] and not it.Empty(RIL.SYMBOL):
                polygon = join_polygons([polygon_from_x0y0x1y1(
                    symbol.BoundingBox(RIL.SYMBOL, padding=self.parameter['padding']))
                                         for symbol in iterate_level(it, RIL.SYMBOL, parent=ril)])
                if ril == RIL.BLOCK:
                    # simulate a RestartBlock(), not defined by Tesseract:
                    it.Begin()
                    for j, it in enumerate(iterate_level(it, RIL.BLOCK)):
                        if index == j:
                            break
                else:
                    it.RestartParagraph()
            else:
                polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, page_coords)
            polygon2 = polygon_for_parent(polygon, region)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            if polygon2 is None:
                self.logger.info('Ignoring extant cell: %s', points)
                continue
            ID = region.id + "_cell%04d" % index
            self.logger.info("Detected cell '%s': %s", ID, points)
            cell = TextRegionType(id=ID, Coords=coords)
            region.add_TextRegion(cell)
            self._add_orientation(it, cell, page_coords)
            if rogroup:
                rogroup.add_RegionRefIndexed(RegionRefIndexedType(regionRef=ID, index=index))
            if self.parameter['textequiv_level'] != 'cell':
                self._process_lines_in_region(it, cell, page_coords, mapping, parent_ril=ril)
            elif self.parameter.get('model', ''):
                cell.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text(ril).rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=it.Confidence(ril)/100.0))

    def _process_lines_in_region(self, result_it, region, page_coords, mapping, parent_ril=RIL.BLOCK):
        if self.parameter['sparse_text']:
            it = result_it
            region.set_type(TextTypeSimpleType.OTHER)
            line = TextLineType(id=region.id + '_line',
                                Coords=region.get_Coords())
            region.add_TextLine(line)
            if self.parameter['textequiv_level'] != 'line':
                self._process_words_in_line(it, line, page_coords, mapping)
            elif self.parameter.get('model', ''):
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text(RIL.TEXTLINE).rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=it.Confidence(RIL.TEXTLINE)/100.0))
            return
        for index, it in enumerate(iterate_level(result_it, RIL.TEXTLINE, parent=parent_ril)):
            bbox = it.BoundingBox(RIL.TEXTLINE, padding=self.parameter['padding'])
            if self.parameter['shrink_polygons'] and not it.Empty(RIL.SYMBOL):
                polygon = join_polygons([polygon_from_x0y0x1y1(
                    symbol.BoundingBox(RIL.SYMBOL, padding=self.parameter['padding']))
                                         for symbol in iterate_level(it, RIL.SYMBOL, parent=RIL.TEXTLINE)])
                it.RestartRow()
            else:
                polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, page_coords)
            polygon2 = polygon_for_parent(polygon, region)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            coords = CoordsType(points=points)
            if polygon2 is None:
                self.logger.info('Ignoring extant line: %s', points)
                continue
            ID = region.id + "_line%04d" % index
            self.logger.info("Detected line '%s': %s", ID, points)
            line = TextLineType(id=ID, Coords=coords)
            region.add_TextLine(line)
            if self.parameter['textequiv_level'] != 'line':
                self._process_words_in_line(it, line, page_coords, mapping)
            elif self.parameter.get('model', ''):
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text(RIL.TEXTLINE).rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=it.Confidence(RIL.TEXTLINE)/100.0))

    def _process_words_in_line(self, result_it, line, coords, mapping):
        for index, it in enumerate(iterate_level(result_it, RIL.WORD)):
            bbox = it.BoundingBox(RIL.WORD, padding=self.parameter['padding'])
            if self.parameter['shrink_polygons'] and not it.Empty(RIL.SYMBOL):
                polygon = join_polygons([polygon_from_x0y0x1y1(
                    symbol.BoundingBox(RIL.SYMBOL, padding=self.parameter['padding']))
                                         for symbol in iterate_level(it, RIL.SYMBOL, parent=RIL.WORD)])
                # simulate a BeginWord(index), not exposed by tesserocr:
                it.RestartRow()
                for j, it in enumerate(iterate_level(it, RIL.WORD)):
                    if index == j:
                        break
            else:
                polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, coords)
            polygon2 = polygon_for_parent(polygon, line)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            if polygon2 is None:
                self.logger.info('Ignoring extant word: %s', points)
                continue
            ID = line.id + "_word%04d" % index
            self.logger.debug("Detected word '%s': %s", ID, points)
            word = WordType(id=ID, Coords=CoordsType(points=points))
            line.add_Word(word)
            if self.parameter['textequiv_level'] != 'word':
                self._process_glyphs_in_word(it, word, coords, mapping)
            elif self.parameter.get('model', ''):
                word.add_TextEquiv(TextEquivType(
                    Unicode=it.GetUTF8Text(RIL.WORD),
                    # iterator scores are arithmetic averages, too
                    conf=it.Confidence(RIL.WORD)/100.0))

    def _process_glyphs_in_word(self, result_it, word, coords, mapping):
        for index, it in enumerate(iterate_level(result_it, RIL.SYMBOL)):
            bbox = it.BoundingBox(RIL.SYMBOL, padding=self.parameter['padding'])
            polygon = polygon_from_x0y0x1y1(bbox)
            polygon = coordinates_for_segment(polygon, None, coords)
            polygon2 = polygon_for_parent(polygon, word)
            if polygon2 is not None:
                polygon = polygon2
            points = points_from_polygon(polygon)
            if polygon2 is None:
                self.logger.info('Ignoring extant glyph: %s', points)
                continue
            ID = word.id + '_glyph%04d' % index
            #self.logger.debug("Detected glyph '%s': %s", ID, points)
            glyph = GlyphType(id=ID, Coords=CoordsType(points))
            word.add_Glyph(glyph)
            if self.parameter['textequiv_level'] != 'glyph':
                pass
            elif self.parameter.get('model', ''):
                glyph_text = it.GetUTF8Text(RIL.SYMBOL) # equals first choice?
                glyph_conf = it.Confidence(RIL.SYMBOL)/100 # equals first choice?
                #self.logger.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
                glyph.add_TextEquiv(TextEquivType(
                    index=0,
                    Unicode=glyph_text,
                    conf=glyph_conf))
                choice_it = it.GetChoiceIterator()
                for choice_no, choice in enumerate(choice_it, 1):
                    alternative_text = choice.GetUTF8Text() or ''
                    alternative_conf = choice.Confidence()/100
                    if alternative_text == glyph_text:
                        continue
                    #self.logger.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                    if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                        choice_no > CHOICE_THRESHOLD_NUM):
                        break
                    # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                    glyph.add_TextEquiv(TextEquivType(
                        index=choice_no,
                        Unicode=alternative_text,
                        conf=alternative_conf))

    def _process_existing_tables(self, tessapi, tables, page, page_image, page_coords, mapping):
        # prepare dict of reading order
        reading_order = dict()
        ro = page.get_ReadingOrder()
        if not ro:
            self.logger.warning("Page contains no ReadingOrder")
            rogroup = None
        else:
            rogroup = ro.get_OrderedGroup() or ro.get_UnorderedGroup()
            page_get_reading_order(reading_order, rogroup)
        segment_only = self.parameter['textequiv_level'] == 'none' or not self.parameter.get('model', '')
        # dive into tables
        for table in tables:
            cells = table.get_TextRegion()
            if cells:
                if not self.parameter['overwrite_segments']:
                    self._process_existing_regions(tessapi, cells, page_image, page_coords, mapping)
                    continue
                self.logger.info('Removing existing TextRegion cells in table %s', table.id)
                for cell in table.get_TextRegion():
                    if cell.id in reading_order:
                        regionref = reading_order[cell.id]
                        self.logger.debug('removing cell %s ref %s', cell.id, regionref.regionRef)
                        # could be any of the 6 types above:
                        regionrefs = regionref.parent_object_.__getattribute__(
                            regionref.__class__.__name__.replace('Type', ''))
                        # remove in-place
                        regionrefs.remove(regionref)
                        del reading_order[cell.id]
                        # TODO: adjust index to make contiguous again?
            table.set_TextRegion([])
            roelem = reading_order.get(table.id)
            if not roelem:
                self.logger.warning("Table '%s' is not referenced in reading order (%s)",
                                    table.id, "no target to add cells into")
            elif isinstance(roelem, (OrderedGroupType, OrderedGroupIndexedType)):
                self.logger.warning("Table '%s' already has an ordered group (%s)",
                                    table.id, "cells will be appended")
            elif isinstance(roelem, (UnorderedGroupType, UnorderedGroupIndexedType)):
                self.logger.warning("Table '%s' already has an unordered group (%s)",
                                    table.id, "cells will not be appended")
                roelem = None
            elif isinstance(roelem, RegionRefIndexedType):
                # replace regionref by group with same index and ref
                # (which can then take the cells as subregions)
                roelem2 = OrderedGroupIndexedType(id=table.id + '_order',
                                                  index=roelem.index,
                                                  regionRef=roelem.regionRef)
                roelem.parent_object_.add_OrderedGroupIndexed(roelem2)
                roelem.parent_object_.get_RegionRefIndexed().remove(roelem)
                roelem = roelem2
            elif isinstance(roelem, RegionRefType):
                # replace regionref by group with same ref
                # (which can then take the cells as subregions)
                roelem2 = OrderedGroupType(id=table.id + '_order',
                                           regionRef=roelem.regionRef)
                roelem.parent_object_.add_OrderedGroup(roelem2)
                roelem.parent_object_.get_RegionRef().remove(roelem)
                roelem = roelem2
            # set table image
            table_image, table_coords = self.workspace.image_from_segment(
                table, page_image, page_coords)
            if not table_image.width or not table_image.height:
                self.logger.warning("Skipping table region '%s' with zero size", table.id)
                continue
            if self.parameter['padding']:
                tessapi.SetImage(pad_image(table_image, self.parameter['padding']))
                table_coords['transform'] = shift_coordinates(
                    table_coords['transform'], 2*[self.parameter['padding']])
            else:
                tessapi.SetImage(table_image)
            tessapi.SetPageSegMode(PSM.SPARSE_TEXT) # retrieve "cells"
            # TODO: we should XY-cut the sparse cells in regroup them into consistent cells
            if segment_only:
                self.logger.debug("Detecting cells in table '%s'", table.id)
                tessapi.AnalyseLayout()
            else:
                self._reinit(tessapi, table, mapping)
                self.logger.debug("Recognizing text in table '%s'", table.id)
                tessapi.Recognize()
            self._process_cells_in_table(tessapi.GetIterator(), table, roelem, table_coords, mapping)
    
    def _process_existing_regions(self, tessapi, regions, page_image, page_coords, mapping):
        if self.parameter['textequiv_level'] in ['region', 'cell'] and not self.parameter.get('model', ''):
            return
        segment_only = self.parameter['textequiv_level'] == 'none' or not self.parameter.get('model', '')
        for region in regions:
            region_image, region_coords = self.workspace.image_from_segment(
                region, page_image, page_coords)
            if not region_image.width or not region_image.height:
                self.logger.warning("Skipping text region '%s' with zero size", region.id)
                continue
            if (region.get_TextEquiv() and not self.parameter['overwrite_text']
                if self.parameter['textequiv_level'] in ['region', 'cell']
                else self.parameter['segmentation_level'] != 'line'):
                pass # image not used here
            elif self.parameter['padding']:
                region_image = pad_image(region_image, self.parameter['padding'])
                tessapi.SetImage(region_image)
                region_coords['transform'] = shift_coordinates(
                    region_coords['transform'], 2*[self.parameter['padding']])
            else:
                tessapi.SetImage(region_image)
            tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
            if not segment_only:
                self._reinit(tessapi, region, mapping)
            # cell (region in table): we could enter from existing_tables or top-level existing regions
            if self.parameter['textequiv_level'] in ['region', 'cell']:
                #if region.get_primaryScript() not in tessapi.GetLoadedLanguages()...
                if region.get_TextEquiv():
                    if not self.parameter['overwrite_text']:
                        continue
                    self.logger.warning("Region '%s' already contained text results", region.id)
                    region.set_TextEquiv([])
                self.logger.debug("Recognizing text in region '%s'", region.id)
                # todo: consider SetParagraphSeparator
                region.add_TextEquiv(TextEquivType(
                    Unicode=tessapi.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=tessapi.MeanTextConf()/100.0))
                continue # next region (to avoid indentation below)
            ## line, word, or glyph level:
            textlines = region.get_TextLine()
            if self.parameter['segmentation_level'] == 'line' and (
                    not textlines or self.parameter['overwrite_segments']):
                if textlines:
                    self.logger.info('Removing existing text lines in region %s', region.id)
                region.set_TextLine([])
                if segment_only:
                    self.logger.debug("Detecting lines in region '%s'", region.id)
                    tessapi.AnalyseLayout()
                else:
                    self.logger.debug("Recognizing text in region '%s'", region.id)
                    tessapi.Recognize()
                self._process_lines_in_region(tessapi.GetIterator(), region, region_coords, mapping)
            elif textlines:
                self._process_existing_lines(tessapi, textlines, region_image, region_coords, mapping)
            else:
                self.logger.warning("Region '%s' contains no text lines (but segmentation is off)",
                                    region.id)

    def _process_existing_lines(self, tessapi, textlines, region_image, region_coords, mapping):
        if self.parameter['textequiv_level'] == 'line' and not self.parameter.get('model', ''):
            return
        segment_only = self.parameter['textequiv_level'] == 'none' or not self.parameter.get('model', '')
        for line in textlines:
            line_image, line_coords = self.workspace.image_from_segment(
                line, region_image, region_coords)
            if not line_image.width or not line_image.height:
                self.logger.warning("Skipping text line '%s' with zero size", line.id)
                continue
            if (line.get_TextEquiv() and not self.parameter['overwrite_text']
                if self.parameter['textequiv_level'] == 'line'
                else self.parameter['segmentation_level'] != 'word'):
                pass # image not used here
            elif self.parameter['padding']:
                line_image = pad_image(line_image, self.parameter['padding'])
                tessapi.SetImage(line_image)
                line_coords['transform'] = shift_coordinates(
                    line_coords['transform'], 2*[self.parameter['padding']])
            else:
                tessapi.SetImage(line_image)
            if self.parameter['raw_lines']:
                tessapi.SetPageSegMode(PSM.RAW_LINE)
            else:
                tessapi.SetPageSegMode(PSM.SINGLE_LINE)
            if not segment_only:
                self._reinit(tessapi, line, mapping)
            #if line.get_primaryScript() not in tessapi.GetLoadedLanguages()...
            if self.parameter['textequiv_level'] == 'line':
                if line.get_TextEquiv():
                    if not self.parameter['overwrite_text']:
                        continue
                    self.logger.warning("Line '%s' already contained text results", line.id)
                    line.set_TextEquiv([])
                self.logger.debug("Recognizing text in line '%s'", line.id)
                # todo: consider BlankBeforeWord, SetLineSeparator
                line.add_TextEquiv(TextEquivType(
                    Unicode=tessapi.GetUTF8Text().rstrip("\n\f"),
                    # iterator scores are arithmetic averages, too
                    conf=tessapi.MeanTextConf()/100.0))
                continue # next line (to avoid indentation below)
            ## word, or glyph level:
            words = line.get_Word()
            if self.parameter['segmentation_level'] == 'word' and (
                    not words or self.parameter['overwrite_segments']):
                if words:
                    self.logger.info('Removing existing words in line %s', line.id)
                line.set_Word([])
                if segment_only:
                    self.logger.debug("Detecting words in line '%s'", line.id)
                    tessapi.AnalyseLayout()
                else:
                    self.logger.debug("Recognizing text in line '%s'", line.id)
                    tessapi.Recognize()
                ## internal word and glyph layout:
                self._process_words_in_line(tessapi.GetIterator(), line, line_coords, mapping)
            elif words:
                ## external word layout:
                self.logger.warning("Line '%s' contains words already, recognition might be suboptimal", line.id)
                self._process_existing_words(tessapi, words, line_image, line_coords, mapping)
            else:
                self.logger.warning("Line '%s' contains no words (but segmentation if off)",
                                    line.id)

    def _process_existing_words(self, tessapi, words, line_image, line_coords, mapping):
        if self.parameter['textequiv_level'] == 'word' and not self.parameter.get('model', ''):
            return
        segment_only = self.parameter['textequiv_level'] == 'none' or not self.parameter.get('model', '')
        for word in words:
            word_image, word_coords = self.workspace.image_from_segment(
                word, line_image, line_coords)
            if not word_image.width or not word_image.height:
                self.logger.warning("Skipping word '%s' with zero size", word.id)
                continue
            if (word.get_TextEquiv() and not self.parameter['overwrite_text']
                if self.parameter['textequiv_level'] == 'word'
                else self.parameter['segmentation_level'] != 'glyph'):
                pass # image not used here
            elif self.parameter['padding']:
                word_image = pad_image(word_image, self.parameter['padding'])
                tessapi.SetImage(word_image)
                word_coords['transform'] = shift_coordinates(
                    word_coords['transform'], 2*[self.parameter['padding']])
            else:
                tessapi.SetImage(word_image)
            tessapi.SetPageSegMode(PSM.SINGLE_WORD)
            if not segment_only:
                self._reinit(tessapi, word, mapping)
            if self.parameter['textequiv_level'] == 'word':
                if word.get_TextEquiv():
                    if not self.parameter['overwrite_text']:
                        continue
                    self.logger.warning("Word '%s' already contained text results", word.id)
                    word.set_TextEquiv([])
                self.logger.debug("Recognizing text in word '%s'", word.id)
                word_conf = tessapi.AllWordConfidences()
                word.add_TextEquiv(TextEquivType(
                    Unicode=tessapi.GetUTF8Text().rstrip("\n\f"),
                    conf=word_conf[0]/100.0 if word_conf else 0.0))
                continue # next word (to avoid indentation below)
            ## glyph level:
            glyphs = word.get_Glyph()
            if self.parameter['segmentation_level'] == 'glyph' and (
                    not glyphs or self.parameter['overwrite_segments']):
                if glyphs:
                    self.logger.info('Removing existing glyphs in word %s', word.id)
                word.set_Glyph([])
                if segment_only:
                    self.logger.debug("Detecting glyphs in word '%s'", word.id)
                    tessapi.AnalyseLayout()
                else:
                    self.logger.debug("Recognizing text in word '%s'", word.id)
                    tessapi.Recognize()
                ## internal glyph layout:
                self._process_glyphs_in_word(tessapi.GetIterator(), word, word_coords, mapping)
            elif glyphs:
                ## external glyph layout:
                self.logger.warning("Word '%s' contains glyphs already, recognition might be suboptimal", word.id)
                self._process_existing_glyphs(tessapi, glyphs, word_image, word_coords, mapping)
            else:
                self.logger.warning("Word '%s' contains no glyphs (but segmentation if off)",
                                    word.id)

    def _process_existing_glyphs(self, tessapi, glyphs, word_image, word_xywh, mapping):
        if not self.parameter.get('model', ''):
            return
        for glyph in glyphs:
            glyph_image, _ = self.workspace.image_from_segment(
                glyph, word_image, word_xywh)
            if not glyph_image.width or not glyph_image.height:
                self.logger.warning("Skipping glyph '%s' with zero size", glyph.id)
                continue
            if glyph.get_TextEquiv() and not self.parameter['overwrite_text']:
                pass # image not used here
            elif self.parameter['padding']:
                tessapi.SetImage(pad_image(glyph_image, self.parameter['padding']))
            else:
                tessapi.SetImage(glyph_image)
            tessapi.SetPageSegMode(PSM.SINGLE_CHAR)
            self._reinit(tessapi, glyph, mapping)
            if glyph.get_TextEquiv():
                if not self.parameter['overwrite_text']:
                    continue
                self.logger.warning("Glyph '%s' already contained text results", glyph.id)
                glyph.set_TextEquiv([])
            self.logger.debug("Recognizing text in glyph '%s'", glyph.id)
            glyph_text = tessapi.GetUTF8Text().rstrip("\n\f")
            glyph_conf = tessapi.AllWordConfidences()
            glyph_conf = glyph_conf[0]/100.0 if glyph_conf else 1.0
            #self.logger.debug('best glyph: "%s" [%f]', glyph_text, glyph_conf)
            glyph.add_TextEquiv(TextEquivType(
                index=0,
                Unicode=glyph_text,
                conf=glyph_conf))
            result_it = tessapi.GetIterator()
            if not result_it or result_it.Empty(RIL.SYMBOL):
                self.logger.error("No text in glyph '%s'", glyph.id)
                continue
            choice_it = result_it.GetChoiceIterator()
            for choice_no, choice in enumerate(choice_it, 1):
                alternative_text = choice.GetUTF8Text()
                alternative_conf = choice.Confidence()/100
                if alternative_text == glyph_text:
                    continue
                #self.logger.debug('alternative glyph: "%s" [%f]', alternative_text, alternative_conf)
                if (glyph_conf - alternative_conf > CHOICE_THRESHOLD_CONF or
                    choice_no > CHOICE_THRESHOLD_NUM):
                    break
                # todo: consider SymbolIsSuperscript (TextStyle), SymbolIsDropcap (RelationType) etc
                glyph.add_TextEquiv(TextEquivType(
                    index=choice_no,
                    Unicode=alternative_text,
                    conf=alternative_conf))
    
    def _add_orientation(self, result_it, region, coords):
        # Tesseract layout analysis already rotates the image, even for each
        # sub-segment (depending on RIL).
        # (These images can be queried via GetBinaryImage/GetImage, cf. segment_region)
        # Unfortunately, it does _not_ use expand=True, but chops off corners.
        # So the accuracy is not as good as setting the image to the sub-segments and
        # running without iterator. But there are other reasons to do all-in-one
        # segmentation (like overlaps), and its up to the user now.
        # Here we don't know whether the iterator will be used or the created PAGE segments.
        # For the latter case at least, we must annotate the angle, so the segment image
        # can be rotated before the next step.
        orientation, writing_direction, textline_order, deskew_angle = result_it.Orientation()
        # defined as 'how many radians does one have to rotate the block anti-clockwise'
        # i.e. positive amount to be applied counter-clockwise for deskewing:
        deskew_angle *= 180 / math.pi
        self.logger.debug('orientation/deskewing for %s: %s / %s / %s / %.3f°', region.id,
                          membername(Orientation, orientation),
                          membername(WritingDirection, writing_direction),
                          membername(TextlineOrder, textline_order),
                          deskew_angle)
        # defined as 'the amount of clockwise rotation to be applied to the input image'
        # i.e. the negative amount to be applied counter-clockwise for deskewing:
        # (as defined in Tesseract OrientationIdToValue):
        angle = {
            Orientation.PAGE_RIGHT: 90,
            Orientation.PAGE_DOWN: 180,
            Orientation.PAGE_LEFT: 270
        }.get(orientation, 0)
        # annotate result:
        angle += deskew_angle
        # get deskewing (w.r.t. top image) already applied to image
        angle0 = coords['angle']
        # page angle: PAGE @orientation is defined clockwise,
        # whereas PIL/ndimage rotation is in mathematical direction:
        orientation = -(angle + angle0)
        orientation = 180 - (180 - orientation) % 360 # map to [-179.999,180]
        region.set_orientation(orientation)
        if isinstance(region, TextRegionType):
            region.set_readingDirection({
                WritingDirection.LEFT_TO_RIGHT: 'left-to-right',
                WritingDirection.RIGHT_TO_LEFT: 'right-to-left',
                WritingDirection.TOP_TO_BOTTOM: 'top-to-bottom'
            }.get(writing_direction, 'bottom-to-top'))
            region.set_textLineOrder({
                TextlineOrder.LEFT_TO_RIGHT: 'left-to-right',
                TextlineOrder.RIGHT_TO_LEFT: 'right-to-left',
                TextlineOrder.TOP_TO_BOTTOM: 'top-to-bottom'
            }.get(textline_order, 'bottom-to-top'))
    
    def _reinit(self, tessapi, segment, mapping):
        """Reset Tesseract API to initial state, and apply API-level settings for the given segment.
        
        If ``xpath_parameters`` is used, try each XPath expression against ``segment``,
        and in case of a match, apply given parameters, respectively.
        
        If ``xpath_model`` is used, try each XPath expression against ``segment``,
        and in case of a match, load the given language/model, respectively.
        
        If ``auto_model`` is used, and no ``xpath_model`` was applied yet,
        try each given language/model individually on ``segment``, compare
        their confidences, and load the best-scoring language/model.
        
        Before returning, store all previous settings (to catch by the next call).
        """
        # Tesseract API is stateful but does not allow copy constructors
        # for segment-by-segment configuration we therefore need to
        # re-initialize the API with the currently loaded settings,
        # and add some custom choices
        node = mapping.get(id(segment), None)
        tag = segment.__class__.__name__[:-4]
        if hasattr(segment, 'id'):
            at_ident = 'id'
        else:
            at_ident = 'imageFilename'
        ident = getattr(segment, at_ident)
        with tessapi:
            # apply temporary changes
            if self.parameter['xpath_parameters']:
                if node is not None and node.attrib.get(at_ident, None) == ident:
                    ns = {'re': 'http://exslt.org/regular-expressions',
                          'pc': node.nsmap[node.prefix],
                          node.prefix: node.nsmap[node.prefix]}
                    for xpath, params in self.parameter['xpath_parameters'].items():
                        if node.xpath(xpath, namespaces=ns):
                            self.logger.info("Found '%s' in '%s', setting '%s'",
                                             xpath, ident, params)
                            for name, val in params.items():
                                tessapi.SetVariable(name, val)
                else:
                    self.logger.error("Cannot find segment '%s' in etree mapping, " \
                                      "ignoring xpath_parameters", ident)
            if self.parameter['xpath_model']:
                if node is not None and node.attrib.get(at_ident, None) == ident:
                    ns = {'re': 'http://exslt.org/regular-expressions',
                          'pc': node.nsmap[node.prefix],
                          node.prefix: node.nsmap[node.prefix]}
                    models = []
                    for xpath, model in self.parameter['xpath_model'].items():
                        if node.xpath(xpath, namespaces=ns):
                            self.logger.info("Found '%s' in '%s', reloading with '%s'",
                                             xpath, ident, model)
                            models.append(model)
                    if models:
                        model = '+'.join(models)
                        self.logger.debug("Reloading model '%s' for %s '%s'", model, tag, ident)
                        tessapi.Reset(lang=model)
                        return
                else:
                    self.logger.error("Cannot find segment '%s' in etree mapping, " \
                                      "ignoring xpath_model", ident)
            if self.parameter['auto_model']:
                models = self.parameter['model'].split('+')
                if len(models) > 1:
                    confs = list()
                    for model in models:
                        tessapi.Reset(lang=model)
                        tessapi.Recognize()
                        confs.append(tessapi.MeanTextConf())
                    model = models[np.argmax(confs)]
                    self.logger.debug("Reloading best model '%s' for %s '%s'", model, tag, ident)
                    tessapi.Reset(lang=model)
                    return
            if self.parameter['xpath_model'] or self.parameter['auto_model']:
                # default: undo all settings from previous calls (reset to init-state)
                tessapi.Reset()

def page_element_unicode0(element):
    """Get Unicode string of the first text result."""
    if element.get_TextEquiv():
        return element.get_TextEquiv()[0].Unicode or ''
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
        
def page_update_higher_textequiv_levels(level, pcgts, overwrite=True):
    """Update the TextEquivs of all PAGE-XML hierarchy levels above ``level`` for consistency.
    
    Starting with the lowest hierarchy level chosen for processing,
    join all first TextEquiv.Unicode (by the rules governing the respective level)
    into TextEquiv.Unicode of the next higher level, replacing them.
    If ``overwrite`` is false and the higher level already has text, keep it.
    
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
                                if not word.get_TextEquiv() or overwrite:
                                    word.set_TextEquiv( # replace old, if any
                                        [TextEquivType(Unicode=word_unicode, conf=word_conf)])
                        line_unicode = ' '.join(page_element_unicode0(word) for word in words)
                        line_conf = sum(page_element_conf0(word) for word in words)
                        if words:
                            line_conf /= len(words)
                        if not line.get_TextEquiv() or overwrite:
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
            if not region.get_TextEquiv() or overwrite:
                region.set_TextEquiv( # replace old, if any
                    [TextEquivType(Unicode=region_unicode, conf=region_conf)])

def page_shrink_higher_coordinate_levels(maxlevel, minlevel, pcgts):
    """Project the coordinate hull of all PAGE-XML hierarchy levels above ``minlevel`` up to ``maxlevel``.
    
    Starting with the lowest hierarchy level chosen for processing,
    join all segments into a convex hull for the next higher level,
    replacing the parent coordinates, respectively.
    
    Follow regions recursively, but make sure to traverse them in a depth-first strategy.
    """
    LOG = getLogger('processor.TesserocrRecognize')
    page = pcgts.get_Page()
    regions = page.get_AllRegions(classes=['Text'])
    if minlevel != 'region':
        for region in regions:
            lines = region.get_TextLine()
            if minlevel != 'line':
                for line in lines:
                    words = line.get_Word()
                    if minlevel != 'word':
                        for word in words:
                            glyphs = word.get_Glyph()
                            if maxlevel in ['region', 'line', 'word', 'glyph'] and glyphs:
                                joint_polygon = join_segments(glyphs)
                                LOG.debug("setting hull for word '%s' from %d vertices",
                                          word.id, len(joint_polygon))
                                word.get_Coords().set_points(points_from_polygon(joint_polygon))
                    if maxlevel in ['region', 'line', 'word'] and words:
                        joint_polygon = join_segments(words)
                        LOG.debug("setting hull for line '%s' from %d vertices",
                                  line.id, len(joint_polygon))
                        line.get_Coords().set_points(points_from_polygon(joint_polygon))
            if maxlevel in ['region', 'line'] and lines:
                joint_polygon = join_segments(lines)
                LOG.debug("setting hull for region '%s' from %d vertices",
                          region.id, len(joint_polygon))
                region.get_Coords().set_points(points_from_polygon(joint_polygon))

def join_segments(segments):
    return join_polygons([polygon_from_points(segment.get_Coords().points)
                          for segment in segments])

def join_polygons(polygons, extend=2):
    # FIXME: construct concave hull / alpha shape
    jointp = unary_union([make_valid(Polygon(polygon)).buffer(extend)
                          for polygon in polygons]).convex_hull
    if jointp.minimum_clearance < 1.0:
        # follow-up calculations will necessarily be integer;
        # so anticipate rounding here and then ensure validity
        jointp = asPolygon(np.round(jointp.exterior.coords))
        jointp = make_valid(jointp)
    return jointp.exterior.coords[:-1]

def pad_image(image, padding):
    # TODO: input padding can create extra edges if not binarized; at least try to smooth
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

def polygon_for_parent(polygon, parent):
    """Clip polygon to parent polygon range.
    
    (Should be moved to ocrd_utils.coordinates_for_segment.)
    """
    childp = Polygon(polygon)
    if isinstance(parent, PageType):
        if parent.get_Border():
            parentp = Polygon(polygon_from_points(parent.get_Border().get_Coords().points))
        else:
            parentp = Polygon([[0, 0], [0, parent.get_imageHeight()],
                               [parent.get_imageWidth(), parent.get_imageHeight()],
                               [parent.get_imageWidth(), 0]])
    else:
        parentp = Polygon(polygon_from_points(parent.get_Coords().points))
    # ensure input coords have valid paths (without self-intersection)
    # (this can happen when shapes valid in floating point are rounded)
    childp = make_valid(childp)
    parentp = make_valid(parentp)
    if not childp.is_valid:
        return None
    if not parentp.is_valid:
        return None
    # check if clipping is necessary
    if childp.within(parentp):
        return childp.exterior.coords[:-1]
    # clip to parent
    interp = childp.intersection(parentp)
    if interp.is_empty or interp.area == 0.0:
        # this happens if Tesseract "finds" something
        # outside of the valid Border of a deskewed/cropped page
        # (empty corners created by masking); will be ignored
        return None
    if interp.type == 'GeometryCollection':
        # heterogeneous result: filter zero-area shapes (LineString, Point)
        interp = unary_union([geom for geom in interp.geoms if geom.area > 0])
    if interp.type == 'MultiPolygon':
        # homogeneous result: construct convex hull to connect
        # FIXME: construct concave hull / alpha shape
        interp = interp.convex_hull
    if interp.minimum_clearance < 1.0:
        # follow-up calculations will necessarily be integer;
        # so anticipate rounding here and then ensure validity
        interp = asPolygon(np.round(interp.exterior.coords))
        interp = make_valid(interp)
    return interp.exterior.coords[:-1] # keep open

def make_valid(polygon):
    for split in range(1, len(polygon.exterior.coords)-1):
        if polygon.is_valid or polygon.simplify(polygon.area).is_valid:
            break
        # simplification may not be possible (at all) due to ordering
        # in that case, try another starting point
        polygon = Polygon(polygon.exterior.coords[-split:]+polygon.exterior.coords[:-split])
    for tolerance in range(1, int(polygon.area)):
        if polygon.is_valid:
            break
        # simplification may require a larger tolerance
        polygon = polygon.simplify(tolerance)
    return polygon

def iterate_level(it, ril, parent=None):
    LOG = getLogger('processor.TesserocrRecognize')
    # improves over tesserocr.iterate_level by
    # honouring multi-level semantics so iterators
    # can be combined across levels
    if parent is None:
        parent = ril - 1
    pos = 0
    while it and not it.Empty(ril):
        yield it
        # With upstream Tesseract, these assertions may fail:
        # if ril > 0 and it.IsAtFinalElement(parent, ril):
        #     for level in range(parent, ril):
        #         assert it.IsAtFinalElement(parent, level), \
        #             "level %d iterator at %d is final w.r.t. %d but level %d is not" % (
        #                 ril, pos, parent, level)
        # Hence the following workaround avails itself:
        if ril > 0 and all(it.IsAtFinalElement(parent, level)
                           for level in range(parent, ril + 1)):
            break
        if not it.Next(ril):
            break
        while it.Empty(ril) and not it.Empty(0):
            # This happens when
            # - on RIL.PARA, RIL.TEXTLINE and RIL.WORD,
            #   empty non-text (pseudo-) blocks intervene
            # - on RIL.SYMBOL, a word has no cblobs at all
            #   (because they have all been rejected)
            # We must _not_ yield these (as they have strange
            # properties and bboxes). But most importantly,
            # they will have met IsAtFinalElement prematurely
            # (hence the similar loop above).
            # Since this may happen multiple consecutive times,
            # enclose this in a while loop.
            LOG.warning("level %d iterator at %d needs to skip empty segment",
                        ril, pos)
            if not it.Next(ril):
                break
        pos += 1
