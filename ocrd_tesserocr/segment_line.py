from __future__ import absolute_import
import tesserocr
from ocrd.utils import getLogger, mets_file_id
from ocrd import Processor, OcrdPage, MIMETYPE_PAGE
from .config import TESSDATA_PREFIX

log = getLogger('processor.TesserocrSegmentLine')

class TesserocrSegmentLine(Processor):

    def process(self):
        """
        Performs the line segmentation.
        """
        with tesserocr.PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                page = OcrdPage.from_file(self.workspace.download_file(input_file))
                image_url = page.imageFileName
                for region in page.list_textregions():
                    log.debug("Detecting lines in %s with tesseract", region)
                    image = self.workspace.resolve_image_as_pil(image_url, region.coords)
                    tessapi.SetImage(image)
                    for component in tessapi.GetComponentImages(tesserocr.RIL.TEXTLINE, True):
                        region.add_textline(coords=component[1])
                self.add_output_file(
                    ID=mets_file_id(self.output_file_grp, n),
                    input_file=input_file,
                    mimetype=MIMETYPE_PAGE,
                    content=page.to_xml()
                )
