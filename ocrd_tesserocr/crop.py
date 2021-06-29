from __future__ import absolute_import
import os.path

import tesserocr
from ocrd_utils import (
    getLogger,
    crop_image,
    coordinates_for_segment,
    coordinates_of_segment,
    bbox_from_polygon,
    bbox_from_points,
    polygon_from_bbox,
    points_from_polygon,
    bbox_from_xywh,
    make_file_id,
    assert_file_grp_cardinality,
    MIMETYPE_PAGE
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    CoordsType, AlternativeImageType,
    to_xml
)
from ocrd_models.ocrd_page_generateds import BorderType
from ocrd import Processor

from .config import get_tessdata_path, OCRD_TOOL
from .recognize import polygon_for_parent

TOOL = 'ocrd-tesserocr-crop'

class TesserocrCrop(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(TesserocrCrop, self).__init__(*args, **kwargs)

    def process(self):
        """Performs page cropping with Tesseract on the workspace.
        
        Open and deserialize PAGE input files and their respective images.
        Set up Tesseract to detect text blocks on each page, and find
        the largest coordinate extent spanning all of them. Use this
        extent in defining a Border, and add that to the page.
        
        Moreover, crop the original image accordingly, and reference the
        resulting image file as AlternativeImage in the Page element.
        
        Add the new image file to the workspace along with the output fileGrp,
        and using a file ID with suffix ``.IMG-CROP`` along with further
        identification of the input element.
        
        Produce new output files by serialising the resulting hierarchy.
        """
        LOG = getLogger('processor.TesserocrCrop')
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)

        with tesserocr.PyTessBaseAPI(path=get_tessdata_path()) as tessapi:
            # disable table detection here (tables count as text blocks),
            # because we do not want to risk confusing the spine with
            # a column separator and thus creeping into a neighbouring
            # page:
            tessapi.SetVariable("textord_tabfind_find_tables", "0")
            for (n, input_file) in enumerate(self.input_files):
                file_id = make_file_id(input_file, self.output_file_grp)
                page_id = input_file.pageId or input_file.ID
                LOG.info("INPUT FILE %i / %s", n, page_id)
                pcgts = page_from_file(self.workspace.download_file(input_file))
                self.add_metadata(pcgts)
                page = pcgts.get_Page()
                
                # warn of existing Border:
                border = page.get_Border()
                if border:
                    left, top, right, bottom = bbox_from_points(border.get_Coords().points)
                    LOG.warning('Overwriting existing Border: %i:%i,%i:%i',
                                left, top, right, bottom)
                
                page_image, page_xywh, page_image_info = self.workspace.image_from_page(
                    page, page_id,
                    # image must not have been cropped already,
                    # abort if no such image can be produced:
                    feature_filter='cropped')
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
                    zoom = 300 / dpi
                else:
                    zoom = 1

                bounds = self.estimate_bounds(page, page_image, tessapi, zoom)
                self.process_page(page, page_image, page_xywh, bounds, file_id, input_file.pageId)

                pcgts.set_pcGtsId(file_id)
                self.workspace.add_file(
                    ID=file_id,
                    file_grp=self.output_file_grp,
                    pageId=input_file.pageId,
                    mimetype=MIMETYPE_PAGE,
                    local_filename=os.path.join(self.output_file_grp,
                                                file_id + '.xml'),
                    content=to_xml(pcgts))
        
    def estimate_bounds(self, page, page_image, tessapi, zoom=1.0):
        """Get outer bounds of all (existing or detected) regions."""
        LOG = getLogger('processor.TesserocrCrop')
        all_left = page_image.width
        all_top = page_image.height
        all_right = 0
        all_bottom = 0
        LOG.info("Cropping with Tesseract")
        tessapi.SetImage(page_image)
        # PSM.SPARSE_TEXT: get as much text as possible in no particular order
        # PSM.AUTO (default): includes tables (dangerous)
        # PSM.SPARSE_TEXT_OSD: sparse but all orientations
        tessapi.SetPageSegMode(tesserocr.PSM.SPARSE_TEXT)
        #
        # iterate over all text blocks and compare their
        # bbox extent to the running min and max values
        for component in tessapi.GetComponentImages(tesserocr.RIL.BLOCK, True):
            image, xywh, index, _ = component
            #
            # the region reference in the reading order element
            #
            ID = "region%04d" % index
            left, top, right, bottom = bbox_from_xywh(xywh)
            LOG.debug("Detected text region '%s': %i:%i,%i:%i",
                      ID, left, right, top, bottom)
            # filter region results:
            bin_bbox = image.getbbox()
            if not bin_bbox:
                # this does happen!
                LOG.info("Ignoring region '%s' because its binarization is empty", ID)
                continue
            width = bin_bbox[2]-bin_bbox[0]
            if width < 25 / zoom:
                # we must be conservative here: page numbers are tiny regions, too!
                LOG.info("Ignoring region '%s' because its width is too small (%d)", ID, width)
                continue
            height = bin_bbox[3]-bin_bbox[1]
            if height < 25 / zoom:
                # we must be conservative here: page numbers are tiny regions, too!
                LOG.debug("Ignoring region '%s' because its height is too small (%d)", ID, height)
                continue
            all_left = min(all_left, left)
            all_top = min(all_top, top)
            all_right = max(all_right, right)
            all_bottom = max(all_bottom, bottom)
        # use existing segmentation as "upper bound"
        regions = page.get_AllRegions(classes=['Text'])
        for region in regions:
            left, top, right, bottom = bbox_from_points(region.get_Coords().points)
            LOG.debug("Found existing text region '%s': %i:%i,%i:%i",
                      region.id, left, right, top, bottom)
            all_left = min(all_left, left)
            all_top = min(all_top, top)
            all_right = max(all_right, right)
            all_bottom = max(all_bottom, bottom)
        LOG.info("Combined page bounds from text regions: %i:%i,%i:%i",
                 all_left, all_right, all_top, all_bottom)
        return all_left, all_top, all_right, all_bottom

    def process_page(self, page, page_image, page_xywh, bounds, file_id, page_id):
        """Set the identified page border, if valid."""
        LOG = getLogger('processor.TesserocrCrop')
        left, top, right, bottom = bounds
        if left >= right or top >= bottom:
            LOG.error("Cannot find valid extent for page '%s'", page_id)
            return
        padding = self.parameter['padding']
        # add padding:
        left = max(left - padding, 0)
        right = min(right + padding, page_image.width)
        top = max(top - padding, 0)
        bottom = min(bottom + padding, page_image.height)
        LOG.info("Padded page border: %i:%i,%i:%i", left, right, top, bottom)
        polygon = polygon_from_bbox(left, top, right, bottom)
        polygon = coordinates_for_segment(polygon, page_image, page_xywh)
        polygon = polygon_for_parent(polygon, page)
        if polygon is None:
            LOG.error("Ignoring extant border")
            return
        border = BorderType(Coords=CoordsType(
            points_from_polygon(polygon)))
        # intersection with parent could have changed bbox,
        # so recalculate:
        bbox = bbox_from_polygon(coordinates_of_segment(border, page_image, page_xywh))
        # update PAGE (annotate border):
        page.set_Border(border)
        # update METS (add the image file):
        page_image = crop_image(page_image, box=bbox)
        page_xywh['features'] += ',cropped'
        file_path = self.workspace.save_image_file(
            page_image, file_id + '.IMG-CROP',
            page_id=page_id, file_grp=self.output_file_grp)
        # update PAGE (reference the image file):
        page.add_AlternativeImage(AlternativeImageType(
            filename=file_path, comments=page_xywh['features']))
    
