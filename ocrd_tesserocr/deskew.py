from __future__ import absolute_import

import os.path
import math
from PIL import Image
from tesserocr import (
    PyTessBaseAPI,
    PSM, OEM,
    Orientation,
    WritingDirection,
    TextlineOrder
)

from ocrd_utils import (
    getLogger,
    make_file_id,
    assert_file_grp_cardinality,
    rotate_image, transpose_image,
    membername,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    AlternativeImageType,
    TextLineType, TextRegionType, PageType,
    to_xml
)
from ocrd import Processor

from .config import get_tessdata_path, OCRD_TOOL

TOOL = 'ocrd-tesserocr-deskew'

class TesserocrDeskew(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrDeskew, self).__init__(*args, **kwargs)

    def process(self):
        """Performs deskewing of the page / region with Tesseract on the workspace.

        Open and deserialise PAGE input files and their respective images,
        then iterate over the element hierarchy down to the region level
        for all text and table regions.

        Set up Tesseract to recognise the region image's orientation, skew
        and script (with both OSD and AnalyseLayout). Rotate the image
        accordingly, and annotate the angle, readingDirection and textlineOrder.
        
        Create a corresponding image file, and reference it as AlternativeImage
        in the element. Add the new image file to the workspace with the fileGrp USE
        given in the second position of the output fileGrp, or ``OCR-D-IMG-DESKEW``,
        and an ID based on input file and input element.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        LOG = getLogger('processor.TesserocrDeskew')
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)
        oplevel = self.parameter['operation_level']
        
        with PyTessBaseAPI(
                path=get_tessdata_path(),
                lang="osd", # osd required for legacy init!
                oem=OEM.TESSERACT_LSTM_COMBINED, # legacy required for OSD!
                psm=PSM.AUTO_OSD
        ) as tessapi:
            if oplevel == 'line':
                tessapi.SetVariable("min_characters_to_try", "15")
            for n, input_file in enumerate(self.input_files):
                file_id = make_file_id(input_file, self.output_file_grp)
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                pcgts.set_pcGtsId(file_id)
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                page_image, page_xywh, page_image_info = self.workspace.image_from_page(
                    page, page_id,
                    # image must not have been rotated already,
                    # (we will overwrite @orientation anyway,)
                    # abort if no such image can be produced:
                    feature_filter='deskewed' if oplevel == 'page' else '')
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
                
                LOG.info("Deskewing on '%s' level in page '%s'", oplevel, page_id)
                
                if oplevel == 'page':
                    self._process_segment(tessapi, page, page_image, page_xywh,
                                          "page '%s'" % page_id, input_file.pageId,
                                          file_id)
                else:
                    regions = page.get_AllRegions(classes=['Text', 'Table'])
                    if not regions:
                        LOG.warning("Page '%s' contains no text regions", page_id)
                    for region in regions:
                        region_image, region_xywh = self.workspace.image_from_segment(
                            region, page_image, page_xywh,
                            # image must not have been rotated already,
                            # (we will overwrite @orientation anyway,)
                            # abort if no such image can be produced:
                            feature_filter='deskewed')
                        if oplevel == 'region':
                            self._process_segment(tessapi, region, region_image, region_xywh,
                                                  "region '%s'" % region.id, input_file.pageId,
                                                  file_id + '_' + region.id)
                        elif isinstance(region, TextRegionType):
                            lines = region.get_TextLine()
                            if not lines:
                                LOG.warning("Page '%s' region '%s' contains no lines", page_id, region.id)
                            for line in lines:
                                line_image, line_xywh = self.workspace.image_from_segment(
                                    line, region_image, region_xywh)
                                self._process_segment(tessapi, line, line_image, line_xywh,
                                                      "line '%s'" % line.id, input_file.pageId,
                                                      file_id + '_' + region.id + '_' + line.id)
                
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp, file_id + '.xml'),
                    content=to_xml(pcgts))
    
    def _process_segment(self, tessapi, segment, image, xywh, where, page_id, file_id):
        LOG = getLogger('processor.TesserocrDeskew')
        if not image.width or not image.height:
            LOG.warning("Skipping %s with zero size", where)
            return
        angle0 = xywh['angle'] # deskewing (w.r.t. top image) already applied to image
        angle = 0. # additional angle to be applied at current level
        tessapi.SetImage(image)
        #tessapi.SetPageSegMode(PSM.AUTO_OSD)
        #
        # orientation/script
        #
        osr = tessapi.DetectOrientationScript()
        if osr:
            assert not math.isnan(osr['orient_conf']), \
                "orientation detection failed (Tesseract probably compiled without legacy OEM, or osd model not installed)"
            if osr['orient_conf'] < self.parameter['min_orientation_confidence']:
                LOG.info('ignoring OSD orientation result %d° clockwise due to low confidence %.0f in %s',
                         osr['orient_deg'], osr['orient_conf'], where)
            else:
                LOG.info('applying OSD orientation result %d° clockwise with high confidence %.0f in %s',
                         osr['orient_deg'], osr['orient_conf'], where)
                # defined as 'the detected clockwise rotation of the input image'
                # i.e. the same amount to be applied counter-clockwise for deskewing:
                angle = osr['orient_deg']
            assert not math.isnan(osr['script_conf']), \
                "script detection failed (Tesseract probably compiled without legacy OEM, or osd model not installed)"
            if osr['script_conf'] < 10:
                LOG.info('ignoring OSD script result "%s" due to low confidence %.0f in %s',
                         osr['script_name'], osr['script_conf'], where)
            else:
                LOG.info('applying OSD script result "%s" with high confidence %.0f in %s',
                         osr['script_name'], osr['script_conf'], where)
                if isinstance(segment, (TextLineType, TextRegionType, PageType)):
                    segment.set_primaryScript({
                        "Arabic": "Arab - Arabic",
                        "Armenian": "Armn - Armenian",
                        "Bengali": "Armn - Armenian",
                        "Canadian_Aboriginal": "Cans - Unified Canadian Aboriginal Syllabics",
                        "Cherokee": "Cher - Cherokee",
                        "Common": "Latn - Latin", # not in scripts/
                        "Cyrillic": "Cyrl - Cyrillic",
                        "Devanagari": "Deva - Devanagari (Nagari)",
                        "Ethiopic": "Ethi - Ethiopic",
                        "Fraktur": "Latf - Latin (Fraktur variant)",
                        "Georgian": "Geor - Georgian (Mkhedruli)",
                        "Greek": "Grek - Greek",
                        "Gujarati": "Gujr - Gujarati",
                        "Gurmukhi": "Guru - Gurmukhi",
                        "Han": "Hant - Han (Traditional variant)", # not in scripts/
                        "Hangul": "Hang - Hangul",
                        "Hangul_vert": "Hang - Hangul",
                        "HanS": "Hans - Han (Simplified variant)",
                        "HanS_vert": "Hans - Han (Simplified variant)",
                        "HanT": "Hant - Han (Traditional variant)",
                        "HanT_vert": "Hant - Han (Traditional variant)",
                        "Hebrew": "Hebr - Hebrew",
                        "Hiragana": "Jpan - Japanese", # not in scripts/
                        "Japanese": "Jpan - Japanese",
                        "Japanese_vert": "Jpan - Japanese",
                        "Kannada": "Knda - Kannada",
                        "Katakana": "Jpan - Japanese", # not in scripts/
                        "Khmer": "Khmr - Khmer",
                        "Lao": "Laoo - Lao",
                        "Latin": "Latn - Latin",
                        "Malayalam": "Mlym - Malayalam",
                        "Myanmar": "Mymr - Myanmar (Burmese)",
                        "Oriya": "Orya - Oriya",
                        "Sinhala": "Sinh - Sinhala",
                        "Syriac": "Syrc - Syriac",
                        "Tamil": "Taml - Tamil",
                        "Telugu": "Telu - Telugu",
                        "Thaana": "Thaa - Thaana",
                        "Thai": "Thai - Thai",
                        "Tibetan": "Tibt - Tibetan",
                        "Vietnamese": "Tavt - Tai Viet",
                    }.get(osr['script_name'], "Latn - Latin"))
        else:
            LOG.warning('no OSD result in %s', where)
        if isinstance(segment, TextLineType):
            return
        #
        # orientation/skew
        #
        layout = tessapi.AnalyseLayout()
        if not layout:
            LOG.warning('no result iterator in %s', where)
            return
        orientation, writing_direction, textline_order, deskew_angle = layout.Orientation()
        if isinstance(segment, (TextRegionType, PageType)):
            segment.set_readingDirection({
                WritingDirection.LEFT_TO_RIGHT: 'left-to-right',
                WritingDirection.RIGHT_TO_LEFT: 'right-to-left',
                WritingDirection.TOP_TO_BOTTOM: 'top-to-bottom'
            }.get(writing_direction, 'bottom-to-top'))
            segment.set_textLineOrder({
                TextlineOrder.LEFT_TO_RIGHT: 'left-to-right',
                TextlineOrder.RIGHT_TO_LEFT: 'right-to-left',
                TextlineOrder.TOP_TO_BOTTOM: 'top-to-bottom'
            }.get(textline_order, 'bottom-to-top'))
        # baseline = layout.Baseline(RIL.BLOCK)
        # if baseline:
        #     points = points_from_x0y0x1y1(list(baseline[0]) + list(baseline[1]))
        #     segment.add_Baseline(BaselineType(points=points))
        # defined as 'how many radians does one have to rotate the block anti-clockwise'
        # i.e. positive amount to be applied counter-clockwise for deskewing:
        deskew_angle *= 180 / math.pi
        LOG.info('orientation/deskewing for %s: %s / %s / %s / %.3f°', where,
                  membername(Orientation, orientation),
                  membername(WritingDirection, writing_direction),
                  membername(TextlineOrder, textline_order),
                  deskew_angle)
        # defined as 'the amount of clockwise rotation to be applied to the input image'
        # i.e. the negative amount to be applied counter-clockwise for deskewing:
        # (as defined in Tesseract OrientationIdToValue):
        angle2 = {
            Orientation.PAGE_RIGHT: 90,
            Orientation.PAGE_DOWN: 180,
            Orientation.PAGE_LEFT: 270
        }.get(orientation, 0)
        if angle2 != angle:
            # This effectively ignores Orientation from AnalyseLayout,
            # because it is usually wrong when it deviates from OSD results.
            # (We do keep deskew_angle, though – see below.)
            # FIXME: revisit that decision after trying with api.set_min_orientation_margin
            LOG.warning('inconsistent angles from layout analysis (%d) and orientation detection (%d) in %s',
                        angle2, angle, where)
        # annotate result:
        angle += deskew_angle
        # page angle: PAGE @orientation is defined clockwise,
        # whereas PIL/ndimage rotation is in mathematical direction:
        orientation = -(angle + angle0)
        orientation = 180 - (180 - orientation) % 360 # map to [-179.999,180]
        segment.set_orientation(orientation) # also removes all deskewed AlternativeImages
        # Tesseract layout analysis already rotates the image, even for each
        # sub-segment (depending on RIL), but the accuracy is not as good
        # as setting the image to the sub-segments and running without iterator.
        # (These images can be queried via GetBinaryImage/GetImage, cf. segment_region)
        # Unfortunately, it does _not_ use expand=True, but chops off corners.
        # So we must do it here from the original image ourselves.
        # We can delegate to OCR-D core for reflection, deskewing and re-cropping:
        if isinstance(segment, PageType):
            image, xywh, _ = self.workspace.image_from_page(
                segment, page_id,
                fill='background', transparency=True)
        else:
            image, xywh = self.workspace.image_from_segment(
                segment, image, xywh,
                fill='background', transparency=True)
        if not angle:
            # zero rotation does not change coordinates,
            # but assures consuming processors that the
            # workflow had deskewing
            xywh['features'] += ',deskewed'
        features = xywh['features'] # features already applied to image
        # update METS (add the image file):
        file_path = self.workspace.save_image_file(
            image, file_id + '.IMG-DESKEW',
            page_id=page_id,
            file_grp=self.output_file_grp)
        # update PAGE (reference the image file):
        segment.add_AlternativeImage(AlternativeImageType(
            filename=file_path, comments=features))
