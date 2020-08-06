from __future__ import absolute_import

import os.path
from tesserocr import RIL, PyTessBaseAPI, PSM

from ocrd import Processor
from ocrd_utils import (
    getLogger, concat_padded,
    make_file_id,
    assert_file_grp_cardinality,
    polygon_from_xywh,
    points_from_polygon,
    coordinates_for_segment,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType,
    LabelType, LabelsType,
    MetadataItemType,
    WordType,
    to_xml,
)

from ocrd_tesserocr.config import TESSDATA_PREFIX, OCRD_TOOL

TOOL = 'ocrd-tesserocr-segment-word'
LOG = getLogger('processor.TesserocrSegmentWord')

class TesserocrSegmentWord(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrSegmentWord, self).__init__(*args, **kwargs)

    def process(self):
        """Performs word segmentation with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the textline level,
        and remove any existing Word elements (unless ``overwrite_words``
        is False).
        
        Set up Tesseract to detect words, and add each one to the line
        at the detected coordinates.
        
        Produce a new output file by serialising the resulting hierarchy.
        """
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        overwrite_words = self.parameter['overwrite_words']

        with PyTessBaseAPI(
            psm=PSM.SINGLE_LINE,
            path=TESSDATA_PREFIX
        ) as tessapi:
            for (n, input_file) in enumerate(self.input_files):
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                page = pcgts.get_Page()
                
                # add metadata about this operation and its runtime parameters:
                metadata = pcgts.get_Metadata() # ensured by from_file()
                metadata.add_MetadataItem(
                    MetadataItemType(type_="processingStep",
                                     name=self.ocrd_tool['steps'][0],
                                     value=TOOL,
                                     Labels=[LabelsType(
                                         externalModel="ocrd-tool",
                                         externalId="parameters",
                                         Label=[LabelType(type_=name,
                                                          value=self.parameter[name])
                                                for name in self.parameter.keys()])]))
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id)
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
                
                for region in page.get_TextRegion():
                    region_image, region_coords = self.workspace.image_from_segment(
                        region, page_image, page_coords)
                    for line in region.get_TextLine():
                        if line.get_Word():
                            if overwrite_words:
                                LOG.info('removing existing Words in line "%s"', line.id)
                                line.set_Word([])
                            else:
                                LOG.warning('keeping existing Words in line "%s"', line.id)
                        LOG.debug("Detecting words in line '%s'", line.id)
                        line_image, line_coords = self.workspace.image_from_segment(
                            line, region_image, region_coords)
                        tessapi.SetImage(line_image)
                        for word_no, component in enumerate(tessapi.GetComponentImages(RIL.WORD, True, raw_image=True)):
                            word_id = '%s_word%04d' % (line.id, word_no)
                            word_polygon = polygon_from_xywh(component[1])
                            word_polygon = coordinates_for_segment(word_polygon, line_image, line_coords)
                            word_points = points_from_polygon(word_polygon)
                            line.add_Word(WordType(
                                id=word_id, Coords=CoordsType(word_points)))
                            
                file_id = make_file_id(input_file, self.output_file_grp)
                pcgts.set_pcGtsId(file_id)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))
