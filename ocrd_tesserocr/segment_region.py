from __future__ import absolute_import
import tesserocr
from ocrd.utils import getLogger, mets_file_id
from ocrd import Processor, OcrdPage, MIMETYPE_PAGE
from .config import TESSDATA_PREFIX

log = getLogger('processor.TesserocrSegmentRegion')

class TesserocrSegmentRegion(Processor):

    def process(self):
        """
        Performs the region segmentation.
        """
        with tesserocr.PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            print (self.input_file_grp)
            for (n, input_file) in enumerate(self.input_files):
                page = OcrdPage.from_file(self.workspace.download_file(input_file))
                image = self.workspace.resolve_image_as_pil(page.imageFileName)
                log.debug("Detecting regions with tesseract")
                tessapi.SetImage(image)
                for component in tessapi.GetComponentImages(tesserocr.RIL.BLOCK, True):
                    box, index = component[1], component[2]
                    # the region reference in the reading order element
                    ID = "r%i" % index
                    page.add_reading_order_ref(ID, index)
                    page.add_textregion(ID, box)
                self.add_output_file(
                    ID=mets_file_id(self.output_file_grp, n),
                    input_file=input_file,
                    mimetype=MIMETYPE_PAGE,
                    content=page.to_xml()
                )
