from __future__ import absolute_import

import os.path
import math
from tesserocr import (
    PyTessBaseAPI,
    PSM, OEM,
    Orientation,
    WritingDirection,
    TextlineOrder
)

from ocrd_utils import (
    getLogger, concat_padded,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    MetadataItemType,
    LabelsType, LabelType,
    AlternativeImageType,
    TextRegionType, PageType,
    to_xml
)
from ocrd import Processor

from .config import TESSDATA_PREFIX, OCRD_TOOL
from .common import (
    image_from_page,
    image_from_region,
    save_image_file,
    membername
)

TOOL = 'ocrd-tesserocr-deskew'
LOG = getLogger('processor.TesserocrDeskew')
FILEGRP_IMG = 'OCR-D-IMG-DESKEW'

class TesserocrDeskew(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrDeskew, self).__init__(*args, **kwargs)

    def process(self):
        """Performs region-level deskewing with Tesseract on the workspace.
        
        Open and deserialise PAGE input files and their respective images,
        then iterate over the element hierarchy down to the region level
        for all text and table regions.
        
        Set up Tesseract to recognise the region image's orientation, skew
        and script (with both OSD and AnalyseLayout). Rotate the image
        accordingly, and annotate the angle, readingDirection and textlineOrder.
        
        Create a cropped (and possibly deskewed) image file, and reference it
        as AlternativeImage in the region element and as file with a fileGrp USE
        equal `OCR-D-IMG-DESKEW` in the workspace.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        oplevel = self.parameter['operation_level']
        with PyTessBaseAPI(
                path=TESSDATA_PREFIX,
                lang="osd", # osd required for legacy init!
                oem=OEM.TESSERACT_LSTM_COMBINED, # legacy required for OSD!
                psm=PSM.AUTO_OSD
        ) as tessapi:
            for n, input_file in enumerate(self.input_files):
                file_id = input_file.ID.replace(self.input_file_grp, FILEGRP_IMG)
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=self.ocrd_tool['steps'][0],
                                     value=TOOL,
                                     # FIXME: externalRef is invalid by pagecontent.xsd, but ocrd does not reflect this
                                     # what we want here is `externalModel="ocrd-tool" externalId="parameters"`
                                     Labels=[LabelsType(#externalRef="parameters",
                                                        Label=[LabelType(type_=name,
                                                                         value=self.parameter[name])
                                                               for name in self.parameter.keys()])]))
                page = pcgts.get_Page()
                page_image = self.workspace.resolve_image_as_pil(page.imageFilename)
                LOG.info("Deskewing on '%s' level in page '%s'", oplevel, page_id)

                page_image, page_xywh = image_from_page(
                    self.workspace, page, page_image, page_id)
                if oplevel == 'page':
                    self._process_segment(tessapi, page, page_image, page_xywh,
                                          "page '%s'" % page_id, input_file.pageId,
                                          file_id)
                else:
                    regions = page.get_TextRegion() + page.get_TableRegion()
                    if not regions:
                        LOG.warning("Page '%s' contains no text regions", page_id)
                    for region in regions:
                        region_image, region_xywh = image_from_region(
                            self.workspace, region, page_image, page_xywh)
                        self._process_segment(tessapi, region, region_image, region_xywh,
                                              "region '%s'" % region.id, input_file.pageId,
                                              file_id + '_' + region.id)

                # Use input_file's basename for the new file -
                # this way the files retain the same basenames:
                file_id = input_file.ID.replace(self.input_file_grp, self.output_file_grp)
                if file_id == input_file.ID:
                    file_id = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))

    def _process_segment(self, tessapi, segment, image, xywh, where, page_id, file_id):
        comments = 'cropped'
        angle = 0.
        tessapi.SetImage(image)
        #tessapi.SetPageSegMode(PSM.AUTO_OSD)
        #
        # orientation/script
        #
        osr = tessapi.DetectOrientationScript()
        if osr:
            assert osr['orient_conf'] and not math.isnan(osr['orient_conf']), \
                "orientation detection failed (Tesseract probably compiled without legacy OEM, or osd model not installed)"
            if osr['orient_conf'] < 10:
                LOG.info('ignoring OSD orientation result %d° due to low confidence %.0f in %s',
                         osr['orient_deg'], osr['orient_conf'], where)
            else:
                LOG.info('applying OSD orientation result %d° with high confidence %.0f in %s',
                         osr['orient_deg'], osr['orient_conf'], where)
                angle = osr['orient_deg']
                if angle:
                    comments += ',rotated-%d' % angle
            assert osr['script_conf'] and not math.isnan(osr['script_conf']), \
                "script detection failed (Tesseract probably compiled without legacy OEM, or osd model not installed)"
            if osr['script_conf'] < 10:
                LOG.info('ignoring OSD script result "%s" due to low confidence %.0f in %s',
                         osr['script_name'], osr['script_conf'], where)
            else:
                LOG.info('applying OSD script  result "%s" with high confidence %.0f in %s',
                         osr['script_name'], osr['script_conf'], where)
                segment.set_primaryScript(osr['script_name'])
        else:
            LOG.warning('no OSD result in %s', where)
        #
        # orientation/skew
        #
        layout = tessapi.AnalyseLayout()
        if layout:
            orientation, writing_direction, textline_order, deskew_angle = layout.Orientation()
            LOG.info('orientation/deskewing for %s: %s / %s / %s / %.3f', where,
                      membername(Orientation, orientation),
                      membername(WritingDirection, writing_direction),
                      membername(TextlineOrder, textline_order),
                      deskew_angle)
            # clockwise rotation, as defined in Tesseract OrientationIdToValue:
            angle2 = {
                Orientation.PAGE_RIGHT: 270,
                Orientation.PAGE_DOWN: 180,
                Orientation.PAGE_LEFT: 90
            }.get(orientation, 0)
            if angle2 != angle:
                LOG.warning('inconsistent angles from layout analysis (%d) and orientation detection (%d) in %s',
                            angle2, angle, where)
            deskew_angle *= - 180 / math.pi
            if int(deskew_angle):
                comments += ',deskewed'
            # if angle:
            #     image = image.transpose({
            #         90: Image.ROTATE_90,
            #         180: Image.ROTATE_180,
            #         270: Image.ROTATE_270
            #     }.get(angle)) # no default
            # angle += deskew_angle
            if angle:
                # Tesseract layout analysis already rotates the image, even for each
                # sub-segment (depending on RIL), but the accuracy is not as good
                # as setting the image to the sub-segments and running without iterator.
                # (These images can be queried via GetBinaryImage/GetImage, cf. segment_region)
                # Unfortunately, it does _not_ use expand=True, but chops off corners.
                # So we must do it here from the original image ourself:
                image = image.rotate(-angle, expand=True, fillcolor='white')
                angle = 180 - (180 - angle) % 360 # map to [-179.999,180]
                # FIXME: remove that condition as soon as PAGE has orientation on PageType:
                if not isinstance(segment, PageType):
                    segment.set_orientation(angle)
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
        # update METS (add the image file):
        file_path = save_image_file(self.workspace, image,
                                    file_id,
                                    page_id=page_id,
                                    file_grp=FILEGRP_IMG)
        # update PAGE (reference the image file):
        segment.add_AlternativeImage(AlternativeImageType(
            filename=file_path, comments=comments))
