from __future__ import absolute_import

import os.path
from tesserocr import (
    PyTessBaseAPI,
    PSM, RIL
)

from ocrd_utils import (
    getLogger,
    assert_file_grp_cardinality,
    make_file_id,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    AlternativeImageType,
    TextRegionType,
    to_xml
)

from .config import OCRD_TOOL
from .recognize import TesserocrRecognize

TOOL = 'ocrd-tesserocr-binarize'

class TesserocrBinarize(TesserocrRecognize):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('ocrd_tool', OCRD_TOOL['tools'][TOOL])
        super().__init__(*args, **kwargs)
        if hasattr(self, 'parameter'):
            self.logger = getLogger('processor.TesserocrBinarize')

    def process(self):
        """Performs binarization of the region / line with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the requested level.
        
        Set up Tesseract to recognize the segment image's layout, and get
        the binarized image. Create an image file, and reference it as
        AlternativeImage in the segment element.
        
        Add the new image file to the workspace along with the output fileGrp,
        and using a file ID with suffix ``.IMG-BIN`` along with further
        identification of the input element.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        sepmask = self.parameter['tiseg']
        oplevel = self.parameter['operation_level']

        with PyTessBaseAPI() as tessapi:
            for n, input_file in enumerate(self.input_files):
                file_id = make_file_id(input_file, self.output_file_grp)
                page_id = input_file.pageId or input_file.ID
                self.logger.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                self.add_metadata(pcgts)
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
                tessapi.SetVariable('user_defined_dpi', str(dpi))
                self.logger.info("Binarizing on '%s' level in page '%s'", oplevel, page_id)

                if oplevel == 'page':
                    tessapi.SetPageSegMode(PSM.AUTO_ONLY)
                    tessapi.SetImage(page_image)
                    if sepmask:
                        # will trigger FindLines() → SegmentPage() → AutoPageSeg()
                        # → SetupPageSegAndDetectOrientation() → FindAndRemoveLines() + FindImages()
                        tessapi.AnalyseLayout()
                    page_image_bin = tessapi.GetThresholdedImage()
                    if page_image_bin:
                        # update METS (add the image file):
                        file_path = self.workspace.save_image_file(page_image_bin,
                                                                   file_id + '.IMG-BIN',
                                                                   page_id=input_file.pageId,
                                                                   file_grp=self.output_file_grp)
                        # update PAGE (reference the image file):
                        features = page_xywh['features'] + ",binarized"
                        if sepmask:
                            features += ",clipped"
                        page.add_AlternativeImage(AlternativeImageType(
                            filename=file_path, comments=features))
                    else:
                        self.logger.error('Cannot binarize %s', "page '%s'" % page_id)
                else:
                    regions = page.get_TextRegion() + page.get_TableRegion()
                    if not regions:
                        self.logger.warning("Page '%s' contains no text regions", page_id)
                    for region in regions:
                        region_image, region_xywh = self.workspace.image_from_segment(
                            region, page_image, page_xywh)
                        if oplevel == 'region':
                            tessapi.SetPageSegMode(PSM.SINGLE_BLOCK)
                            self._process_segment(tessapi, RIL.BLOCK, region, region_image, region_xywh,
                                                  "region '%s'" % region.id, input_file.pageId,
                                                  file_id + '_' + region.id)
                        elif isinstance(region, TextRegionType):
                            lines = region.get_TextLine()
                            if not lines:
                                self.logger.warning("Page '%s' region '%s' contains no text lines",
                                                    page_id, region.id)
                            for line in lines:
                                line_image, line_xywh = self.workspace.image_from_segment(
                                    line, region_image, region_xywh)
                                tessapi.SetPageSegMode(PSM.SINGLE_LINE)
                                self._process_segment(tessapi, RIL.TEXTLINE, line, line_image, line_xywh,
                                                      "line '%s'" % line.id, input_file.pageId,
                                                      file_id + '_' + region.id + '_' + line.id)

                file_id = make_file_id(input_file, self.output_file_grp)
                pcgts.set_pcGtsId(file_id)
                self.workspace.add_file(
                    file_id=file_id,
                    file_grp=self.output_file_grp,
                    page_id=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_segment(self, tessapi, ril, segment, image, xywh, where, page_id, file_id):
        tessapi.SetImage(image)
        image_bin = None
        layout = tessapi.AnalyseLayout()
        if layout:
            image_bin = layout.GetBinaryImage(ril)
        if not image_bin:
            self.logger.error('Cannot binarize %s', where)
            return
        # update METS (add the image file):
        file_path = self.workspace.save_image_file(image_bin,
                                    file_id + '.IMG-BIN',
                                    page_id=page_id,
                                    file_grp=self.output_file_grp)
        # update PAGE (reference the image file):
        features = xywh['features'] + ",binarized"
        segment.add_AlternativeImage(AlternativeImageType(
            filename=file_path, comments=features))
