from __future__ import absolute_import

import os.path
from typing import Optional

import tesserocr

from ocrd_utils import (
    crop_image,
    coordinates_for_segment,
    coordinates_of_segment,
    bbox_from_polygon,
    bbox_from_points,
    polygon_from_bbox,
    points_from_polygon,
    bbox_from_xywh,
)
from ocrd_models.ocrd_page import (
    CoordsType,
    AlternativeImageType,
    BorderType,
    OcrdPage
)
from ocrd.processor import OcrdPageResult, OcrdPageResultImage

from .recognize import TesserocrRecognize
from .common import polygon_for_parent

class TesserocrCrop(TesserocrRecognize):
    @property
    def executable(self):
        return 'ocrd-tesserocr-crop'

    def _init(self):
        # use default model (eng) with vanilla tesserocr API
        self.tessapi = tesserocr.PyTessBaseAPI()
        # disable table detection here (tables count as text blocks),
        # because we do not want to risk confusing the spine with
        # a column separator and thus creeping into a neighbouring
        # page:
        self.tessapi.SetVariable("textord_tabfind_find_tables", "0")

    def process_page_pcgts(self, *input_pcgts: Optional[OcrdPage], page_id: str = None) -> OcrdPageResult:
        """Performs page cropping with Tesseract on the workspace.

        Open and deserialize PAGE input file and its respective images.
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
        pcgts = input_pcgts[0]
        result = OcrdPageResult(pcgts)
        page = pcgts.get_Page()
                
        # warn of existing Border:
        border = page.get_Border()
        if border:
            left, top, right, bottom = bbox_from_points(border.get_Coords().points)
            self.logger.warning('Overwriting existing Border: %i:%i,%i:%i',
                                left, top, right, bottom)

        page_image, page_xywh, page_image_info = self.workspace.image_from_page(
            page, page_id,
            # image must not have been cropped already,
            # abort if no such image can be produced:
            feature_filter='cropped')
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
        if dpi:
            zoom = 300 / dpi
        else:
            zoom = 1

        bounds = self._estimate_bounds(page, page_image, zoom)
        cropped = self._process_page(page, page_image, page_xywh, bounds)
        if cropped:
            result.images.append(cropped)
        return result
        
    def _estimate_bounds(self, page, page_image, zoom=1.0):
        """Get outer bounds of all (existing or detected) regions."""
        all_left = page_image.width
        all_top = page_image.height
        all_right = 0
        all_bottom = 0
        self.logger.info("Cropping with Tesseract")
        self.tessapi.SetImage(page_image)
        # PSM.SPARSE_TEXT: get as much text as possible in no particular order
        # PSM.AUTO (default): includes tables (dangerous)
        # PSM.SPARSE_TEXT_OSD: sparse but all orientations
        self.tessapi.SetPageSegMode(tesserocr.PSM.SPARSE_TEXT)
        #
        # iterate over all text blocks and compare their
        # bbox extent to the running min and max values
        for component in self.tessapi.GetComponentImages(tesserocr.RIL.BLOCK, True):
            image, xywh, index, _ = component
            #
            # the region reference in the reading order element
            #
            ID = "region%04d" % index
            left, top, right, bottom = bbox_from_xywh(xywh)
            self.logger.debug("Detected text region '%s': %i:%i,%i:%i",
                              ID, left, right, top, bottom)
            # filter region results:
            bin_bbox = image.getbbox()
            if not bin_bbox:
                # this does happen!
                self.logger.warning("Ignoring region '%s' because its binarization is empty", ID)
                continue
            width = bin_bbox[2]-bin_bbox[0]
            if width < 25 / zoom:
                # we must be conservative here: page numbers are tiny regions, too!
                self.logger.warning("Ignoring region '%s' because its width is too small (%d)", ID, width)
                continue
            height = bin_bbox[3]-bin_bbox[1]
            if height < 25 / zoom:
                # we must be conservative here: page numbers are tiny regions, too!
                self.logger.warning("Ignoring region '%s' because its height is too small (%d)", ID, height)
                continue
            all_left = min(all_left, left)
            all_top = min(all_top, top)
            all_right = max(all_right, right)
            all_bottom = max(all_bottom, bottom)
        # use existing segmentation as "upper bound"
        regions = page.get_AllRegions(classes=['Text'])
        for region in regions:
            left, top, right, bottom = bbox_from_points(region.get_Coords().points)
            self.logger.debug("Found existing text region '%s': %i:%i,%i:%i",
                              region.id, left, right, top, bottom)
            all_left = min(all_left, left)
            all_top = min(all_top, top)
            all_right = max(all_right, right)
            all_bottom = max(all_bottom, bottom)
        self.logger.info("Combined page bounds from text regions: %i:%i,%i:%i",
                         all_left, all_right, all_top, all_bottom)
        return all_left, all_top, all_right, all_bottom

    def _process_page(self, page, page_image, page_xywh, bounds) -> Optional[OcrdPageResultImage]:
        """Set the identified page border, if valid."""
        left, top, right, bottom = bounds
        if left >= right or top >= bottom:
            self.logger.error("Cannot find valid extent for page")
            return None
        padding = self.parameter['padding']
        # add padding:
        left = max(left - padding, 0)
        right = min(right + padding, page_image.width)
        top = max(top - padding, 0)
        bottom = min(bottom + padding, page_image.height)
        self.logger.info("Padded page border: %i:%i,%i:%i", left, right, top, bottom)
        polygon = polygon_from_bbox(left, top, right, bottom)
        polygon = coordinates_for_segment(polygon, page_image, page_xywh)
        polygon = polygon_for_parent(polygon, page)
        if polygon is None:
            self.logger.error("Ignoring extant border")
            return None
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
        # update PAGE (reference the image file):
        alt_image = AlternativeImageType(comments=page_xywh['features'])
        page.add_AlternativeImage(alt_image)
        return OcrdPageResultImage(page_image, '.IMG-CROP', alt_image)
