from __future__ import absolute_import

import locale

# pylint: disable=wrong-import-position
locale.setlocale(locale.LC_ALL, 'C') # circumvent tesseract-ocr issue 1670 (which cannot be done on command line because Click requires an UTF-8 locale in Python 3)

from tesserocr import RIL, PSM, PyTessBaseAPI

from ocrd_utils import getLogger, concat_padded, xywh_from_points, points_from_x0y0x1y1, MIMETYPE_PAGE
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,
    GlyphType,
    LabelType,
    LabelsType,
    MetadataItemType,
    TextEquivType,
    TextStyleType,

    to_xml
)
from ocrd import Processor
from .config import TESSDATA_PREFIX, OCRD_TOOL

log = getLogger('processor.TesserocrDeskew')

class TesserocrDeskew(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-deskew']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrDeskew, self).__init__(*args, **kwargs)

    def process(self):
        """
        Performs the deskewing.
        """
        # print(self.parameter)
        oplevel = self.parameter['operation_level']
        with PyTessBaseAPI(path=TESSDATA_PREFIX, psm=PSM.AUTO_OSD) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                log.info("INPUT FILE %i / %s", n, input_file)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                pil_image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)

                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=OCRD_TOOL['tools']['ocrd-tesserocr-deskew']['steps'][0],
                                     value='ocrd-tesserocr-deskew',
                                     Labels=[LabelsType(externalRef="parameters",
                                                        Label=[LabelType(type_=name,
                                                                         value=self.parameter[name])
                                                               for name in self.parameter.keys()])]))
                log.info("Deskewing on '%s' level on page '%s'", oplevel, pcgts.get_pcGtsId())

                if oplevel == 'page':
                    self._process_page(tessapi, pil_image)
                elif oplevel == 'region': 
                    regions = pcgts.get_Page().get_TextRegion()
                    if not regions:
                        log.warning("Deskewing regions requested but page contains no text regions")
                    self._process_regions(regions, tessapi, pil_image)

                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    mimetype=MIMETYPE_PAGE,
                    local_filename='%s/%s' % (self.output_file_grp, ID),
                    content=to_xml(pcgts),
                )

    def _process_page(self, tessapi, pil_image):
        tessapi.SetImage(pil_image)
        orientation, direction, order, deskew_angle = tessapi.AnalyseLayout().Orientation()
        log.debug("Deskew angle: {:.4f}".format(deskew_angle))

    def _process_regions(self, regions, tessapi, pil_image):
        for region in regions:
            log.debug("Deskewing region '%s'", region.id)
            region_xywh = xywh_from_points(region.get_Coords().points)

            # Note: we set the image instead of specifying a rectangle!
            pil_region_image = pil_image.crop((region_xywh['x'], region_xywh['y'], region_xywh['x'] + region_xywh['w'], region_xywh['y'] + region_xywh['h']))
            tessapi.SetImage(pil_region_image)

            orientation, direction, order, deskew_angle = tessapi.AnalyseLayout().Orientation()
            log.debug("Deskew angle: {:.4f}".format(deskew_angle))
            region.set_orientation(deskew_angle)
