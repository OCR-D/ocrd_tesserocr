from __future__ import absolute_import

import os.path
from tesserocr import (
    PyTessBaseAPI,
    PSM, RIL
)

from ocrd_models.ocrd_page import (
    AlternativeImageType,
    TextRegionType,
)

from .recognize import TesserocrRecognize

class TesserocrBinarize(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-binarize'

    def _init(self):
        # use default model (eng) with vanilla tesserocr API
        self.tessapi = PyTessBaseAPI()

    def process_page_pcgts(self, pcgts, output_file_id=None, page_id=None):
        """Performs binarization of the region / line with Tesseract on the workspace.
        
        Open and deserialize PAGE input file and its respective images,
        then iterate over the element hierarchy down to the requested level.
        
        Set up Tesseract to recognize the segment image's layout, and get
        the binarized image. Create an image file, and reference it as
        AlternativeImage in the segment element.
        
        Add the new image file to the workspace along with the output fileGrp,
        and using a file ID with suffix ``.IMG-BIN`` along with further
        identification of the input element.
        
        Produce a new output file by serialising the resulting hierarchy.
        """

        sepmask = self.parameter['tiseg']
        oplevel = self.parameter['operation_level']

        page = pcgts.get_Page()
        page_image, page_xywh, page_image_info = self.workspace.image_from_page(
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
        self.logger.info("Binarizing on '%s' level in page '%s'", oplevel, page_id)

        if oplevel == 'page':
            image = self._process_segment(-1, page, page_image, page_xywh,
                                          page_id, output_file_id)
            if image:
                return [pcgts, image]
            else:
                return pcgts

        result = [pcgts]
        regions = page.get_AllRegions(classes=['Text', 'Table'])
        if not regions:
            self.logger.warning("Page '%s' contains no text regions", page_id)
        for region in regions:
            region_image, region_xywh = self.workspace.image_from_segment(
                region, page_image, page_xywh)
            if oplevel == 'region':
                image = self._process_segment(RIL.BLOCK, region, region_image, region_xywh,
                                              "region '%s'" % region.id,
                                              output_file_id + '_' + region.id)
                if image:
                    result.append(image)
            elif isinstance(region, TextRegionType):
                lines = region.get_TextLine()
                if not lines:
                    self.logger.warning("Page '%s' region '%s' contains no text lines",
                                        page_id, region.id)
                for line in lines:
                    line_image, line_xywh = self.workspace.image_from_segment(
                        line, region_image, region_xywh)
                    image = self._process_segment(RIL.TEXTLINE, line, line_image, line_xywh,
                                                  "line '%s'" % line.id,
                                                  output_file_id + '_' + region.id + '_' + line.id)
                    if image:
                        result.append(image)

        return result

    def _process_segment(self, ril, segment, image, xywh, where, file_id):
        self.tessapi.SetImage(image)
        features = xywh['features'] + ",binarized"
        image_bin = None
        if ril == -1:
            # page level
            self.tessapi.SetPageSegMode(PSM.AUTO_ONLY)
            if self.parameter['tiseg']:
                features += ",clipped"
                # will trigger FindLines() → SegmentPage() → AutoPageSeg()
                # → SetupPageSegAndDetectOrientation() → FindAndRemoveLines() + FindImages()
                self.tessapi.AnalyseLayout()
            image_bin = self.tessapi.GetThresholdedImage()
        else:
            if ril == RIL.BLOCK:
                self.tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
            if ril == RIL.TEXTLINE:
                self.tessapi.SetPageSegMode(PSM.SINGLE_LINE)
            layout = self.tessapi.AnalyseLayout()
            if layout:
                image_bin = layout.GetBinaryImage(ril)
        if not image_bin:
            self.logger.error('Cannot binarize %s', where)
            return False
        # update METS (add the image file):
        file_id += '.IMG-BIN'
        file_path = os.path.join(self.output_file_grp, file_id + '.png')
        # update PAGE (reference the image file):
        segment.add_AlternativeImage(AlternativeImageType(
            filename=file_path, comments=features))
        return image_bin, file_id, file_path
