from __future__ import absolute_import

from typing import Optional
import os.path
import math

from tesserocr import (
    PyTessBaseAPI,
    PSM, OEM,
    Orientation,
    WritingDirection,
    TextlineOrder
)

from ocrd_utils import membername
from ocrd_models.ocrd_page import (
    AlternativeImageType,
    TextLineType, 
    TextRegionType, 
    PageType,
    OcrdPage
)
from ocrd.processor import OcrdPageResult, OcrdPageResultImage

from .recognize import TesserocrRecognize


class TesserocrDeskew(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-deskew'

    def _init(self):
        # use default model (eng) with vanilla tesserocr API
        self.tessapi = PyTessBaseAPI(lang="osd", # osd required for legacy init!
                                     oem=OEM.TESSERACT_LSTM_COMBINED, # legacy required for OSD!
                                     psm=PSM.AUTO_OSD)
        if self.parameter['operation_level'] == 'line':
            self.tessapi.SetVariable("min_characters_to_try", "15")

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: Optional[str] = None) -> OcrdPageResult:
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
        oplevel = self.parameter['operation_level']
        pcgts = input_pcgts[0]
        page = pcgts.get_Page()
        result = OcrdPageResult(pcgts)
                
        page_image, page_xywh, page_image_info = self.workspace.image_from_page(
            page, page_id,
            # image must not have been rotated already,
            # (we will overwrite @orientation anyway,)
            # abort if no such image can be produced:
            feature_filter='deskewed' if oplevel == 'page' else '')
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
                
        self.logger.info("Deskewing on '%s' level in page '%s'", oplevel, page_id)

        if oplevel == 'page':
            image = self._process_segment(page, page_image, page_xywh,
                                          "page '%s'" % page_id)
            if image:
                result.images.append(image)
            return result

        regions = page.get_AllRegions(classes=['Text', 'Table'])
        if not regions:
            self.logger.warning("Page '%s' contains no text regions", page_id)
        for region in regions:
            region_image, region_xywh = self.workspace.image_from_segment(
                region, page_image, page_xywh,
                # image must not have been rotated already,
                # (we will overwrite @orientation anyway,)
                # abort if no such image can be produced:
                feature_filter='deskewed')
            if oplevel == 'region':
                image = self._process_segment(region, region_image, region_xywh,
                                              "region '%s'" % region.id)
                if image:
                    result.images.append(image)
            elif isinstance(region, TextRegionType):
                lines = region.get_TextLine()
                if not lines:
                    self.logger.warning("Page '%s' region '%s' contains no lines", page_id, region.id)
                for line in lines:
                    line_image, line_xywh = self.workspace.image_from_segment(
                        line, region_image, region_xywh)
                    image = self._process_segment(line, line_image, line_xywh,
                                                  "line '%s'" % line.id)
                    if image:
                        result.images.append(image)
        return result

    def _process_segment(self, segment, image, xywh, where):
        if not image.width or not image.height:
            self.logger.warning("Skipping %s with zero size", where)
            return None
        angle0 = xywh['angle'] # deskewing (w.r.t. top image) already applied to image
        angle = 0. # additional angle to be applied at current level
        self.tessapi.SetImage(image)
        #self.tessapi.SetPageSegMode(PSM.AUTO_OSD)
        #
        # orientation/script
        #
        osr = self.tessapi.DetectOrientationScript()
        if osr:
            assert not math.isnan(osr['orient_conf']), \
                "orientation detection failed (Tesseract probably compiled without legacy OEM, or osd model not installed)"
            if osr['orient_conf'] < self.parameter['min_orientation_confidence']:
                self.logger.info('ignoring OSD orientation result %d° clockwise due to low confidence %.0f in %s',
                                 osr['orient_deg'], osr['orient_conf'], where)
            else:
                self.logger.info('applying OSD orientation result %d° clockwise with high confidence %.0f in %s',
                                 osr['orient_deg'], osr['orient_conf'], where)
                # defined as 'the detected clockwise rotation of the input image'
                # i.e. the same amount to be applied counter-clockwise for deskewing:
                angle = osr['orient_deg']
            assert not math.isnan(osr['script_conf']), \
                "script detection failed (Tesseract probably compiled without legacy OEM, or osd model not installed)"
            if osr['script_conf'] < 10:
                self.logger.info('ignoring OSD script result "%s" due to low confidence %.0f in %s',
                                 osr['script_name'], osr['script_conf'], where)
            else:
                self.logger.info('applying OSD script result "%s" with high confidence %.0f in %s',
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
            self.logger.warning('no OSD result in %s', where)
        if isinstance(segment, TextLineType):
            return None
        #
        # orientation/skew
        #
        layout = self.tessapi.AnalyseLayout()
        if not layout:
            self.logger.warning('no result iterator in %s', where)
            return None
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
        self.logger.info('orientation/deskewing for %s: %s / %s / %s / %.3f°', where,
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
            self.logger.warning('inconsistent angles from layout analysis (%d) and orientation detection (%d) in %s',
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
                segment, where,
                fill='background', transparency=True)
            suffix = '.IMG-DESKEW'
        else:
            image, xywh = self.workspace.image_from_segment(
                segment, image, xywh,
                fill='background', transparency=True)
            suffix = segment.id + '.IMG-DESKEW'
        if not angle:
            # zero rotation does not change coordinates,
            # but assures consuming processors that the
            # workflow had deskewing
            xywh['features'] += ',deskewed'
        features = xywh['features'] # features already applied to image
        # update PAGE (reference the image file):
        alternative = AlternativeImageType(comments=features)
        segment.add_AlternativeImage(alternative)
        return OcrdPageResultImage(image, suffix, alternative)
