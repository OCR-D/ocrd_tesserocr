from __future__ import absolute_import
import tesserocr
from ocrd_utils import getLogger, concat_padded, points_from_xywh, MIMETYPE_PAGE
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,

    to_xml
)
from ocrd_models.ocrd_page_generateds import BorderType

from ocrd import Processor

from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

log = getLogger('processor.TesserocrCrop')

class TesserocrCrop(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-tesserocr-crop']
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrCrop, self).__init__(*args, **kwargs)

    def process(self):
        """
        Performs the cropping.
        """
        with tesserocr.PyTessBaseAPI(path=TESSDATA_PREFIX) as tessapi:
            #  print(self.input_file_grp)
            for (n, input_file) in enumerate(self.input_files):
                #  print(input_file)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                image = self.workspace.resolve_image_as_pil(pcgts.get_Page().imageFilename)
                log.debug("Cropping with tesseract")
                tessapi.SetImage(image)
                
                #
                # helper variables for saving the box coordinates
                #
                min_x = image.width
                min_y = image.height
                max_x = 0
                max_y = 0

                # iterate over all boxes and compare their extent
                # to the min and max values
                for component in tessapi.GetComponentImages(tesserocr.RIL.BLOCK, True):
                    points, index = points_from_xywh(component[1]), component[2]

                    #
                    # the region reference in the reading order element
                    #
                    ID = "region%04d" % index
                    log.debug("Detected region '%s': %s", ID, points)

                    for pair in points.split(' '):
                        x, y = (int(pair.split(',')[0]), int(pair.split(',')[1]))
                        if x < min_x:
                            min_x = x
                        if y < min_y:
                            min_y = y
                        elif x > max_x:
                            max_x = x
                        elif y > max_y:
                            max_y = y
                    log.debug("Updated page border: %i,%i %i,%i %i,%i %i,%i" % (min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y))

                #
                # set the identified page border
                #
                brd = BorderType(Coords=CoordsType("%i,%i %i,%i %i,%i %i,%i" % (min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y)))
                pcgts.get_Page().set_Border(brd)

                ID = concat_padded(self.output_file_grp, n)
                self.workspace.add_file(
                    ID=ID,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename='%s/%s' % (self.output_file_grp, ID),
                    content=to_xml(pcgts).encode('utf-8'),
                )
