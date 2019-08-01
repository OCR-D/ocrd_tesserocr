from __future__ import absolute_import

import os.path
import io

import numpy as np

from ocrd_models import OcrdExif
from ocrd_utils import (
    getLogger,
    coordinates_of_segment,
    xywh_from_points,
    polygon_from_points,
    image_from_polygon,
    crop_image,
)

LOG = getLogger('') # to be refined by importer


# to be refactored into core (as method of ocrd.workspace.Workspace):
# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_page(workspace, page, page_id):
    """Extract the Page image from the workspace.
    
    Given a PageType object, `page`, extract its PIL.Image from
    AlternativeImage if it exists. Otherwise extract the PIL.Image
    from imageFilename and crop it if a Border exists. Otherwise
    just return it.
    
    When cropping, respect any orientation angle annotated for
    the page (from page-level deskewing) by rotating the
    cropped image, respectively.
    
    If the resulting page image is larger than the bounding box of
    `page`, pass down the page's box coordinates with an offset of
    half the width/height difference.
    
    Return the extracted image, and the absolute coordinates of
    the page's bounding box / border (for passing down), and
    an OcrdExif instance associated with the original image.
    """
    page_image = workspace.resolve_image_as_pil(page.imageFilename)
    page_image_info = OcrdExif(page_image)
    page_xywh = {'x': 0,
                 'y': 0,
                 'w': page_image.width,
                 'h': page_image.height}
    # region angle: PAGE orientation is defined clockwise,
    # whereas PIL/ndimage rotation is in mathematical direction:
    page_xywh['angle'] = -(page.get_orientation() or 0)
    # FIXME: remove PrintSpace here as soon as GT abides by the PAGE standard:
    border = page.get_Border() or page.get_PrintSpace()
    if border:
        page_points = border.get_Coords().points
        LOG.debug("Using explictly set page border '%s' for page '%s'",
                  page_points, page_id)
        page_xywh = xywh_from_points(page_points)
    
    alternative_image = page.get_AlternativeImage()
    if alternative_image:
        # (e.g. from page-level cropping, binarization, deskewing or despeckling)
        # assumes implicit cropping (i.e. page_xywh has been applied already)
        LOG.debug("Using AlternativeImage %d (%s) for page '%s'",
                  len(alternative_image), alternative_image[-1].get_comments(),
                  page_id)
        page_image = workspace.resolve_image_as_pil(
            alternative_image[-1].get_filename())
    elif border:
        # get polygon outline of page border:
        page_polygon = np.array(polygon_from_points(page_points))
        # create a mask from the page polygon:
        page_image = image_from_polygon(page_image, page_polygon)
        # recrop into page rectangle:
        page_image = crop_image(page_image,
            box=(page_xywh['x'],
                 page_xywh['y'],
                 page_xywh['x'] + page_xywh['w'],
                 page_xywh['y'] + page_xywh['h']))
        if 'angle' in page_xywh and page_xywh['angle']:
            LOG.info("About to rotate page '%s' by %.2f°",
                      page_id, page_xywh['angle'])
            page_image = page_image.rotate(page_xywh['angle'],
                                               expand=True,
                                               #resample=Image.BILINEAR,
                                               fillcolor='white')
    # subtract offset from any increase in binary region size over source:
    page_xywh['x'] -= round(0.5 * max(0, page_image.width  - page_xywh['w']))
    page_xywh['y'] -= round(0.5 * max(0, page_image.height - page_xywh['h']))
    return page_image, page_xywh, page_image_info

# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_segment(workspace, segment, parent_image, parent_xywh):
    """Extract a segment image from its parent's image.
    
    Given a PIL.Image of the parent, `parent_image`, and
    its absolute coordinates, `parent_xywh`, and a PAGE
    segment (TextRegion / TextLine / Word / Glyph) object
    logically contained in it, `segment`, extract its PIL.Image
    from AlternativeImage (if it exists), or via cropping from
    `parent_image`.
    
    When cropping, respect any orientation angle annotated for
    the parent (from parent-level deskewing) by compensating the
    segment coordinates in an inverse transformation (translation
    to center, rotation, re-translation).
    Also, mind the difference between annotated and actual size
    of the parent (usually from deskewing), by a respective offset
    into the image. Cropping uses a polygon mask (not just the
    rectangle).
    
    When cropping, respect any orientation angle annotated for
    the segment (from segment-level deskewing) by rotating the
    cropped image, respectively.
    
    If the resulting segment image is larger than the bounding box of
    `segment`, pass down the segment's box coordinates with an offset
    of half the width/height difference.
    
    Return the extracted image, and the absolute coordinates of
    the segment's bounding box (for passing down).
    """
    segment_xywh = xywh_from_points(segment.get_Coords().points)
    if 'orientation' in segment.__dict__:
        # angle: PAGE orientation is defined clockwise,
        # whereas PIL/ndimage rotation is in mathematical direction:
        segment_xywh['angle'] = -(segment.get_orientation() or 0)
    alternative_image = segment.get_AlternativeImage()
    if alternative_image:
        # (e.g. from segment-level cropping, binarization, deskewing or despeckling)
        LOG.debug("Using AlternativeImage %d (%s) for segment '%s'",
                  len(alternative_image), alternative_image[-1].get_comments(),
                  segment.id)
        segment_image = workspace.resolve_image_as_pil(
            alternative_image[-1].get_filename())
    else:
        # get polygon outline of segment relative to parent image:
        segment_polygon = coordinates_of_segment(segment, parent_image, parent_xywh)
        # create a mask from the segment polygon:
        segment_image = image_from_polygon(parent_image, segment_polygon)
        # recrop into segment rectangle:
        segment_image = crop_image(segment_image,
            box=(segment_xywh['x'] - parent_xywh['x'],
                 segment_xywh['y'] - parent_xywh['y'],
                 segment_xywh['x'] - parent_xywh['x'] + segment_xywh['w'],
                 segment_xywh['y'] - parent_xywh['y'] + segment_xywh['h']))
        # note: We should mask overlapping neighbouring segments here,
        # but finding the right clipping rules can be difficult if operating
        # on the raw (non-binary) image data alone: for each intersection, it
        # must be decided which one of either segment or neighbour to assign,
        # e.g. an ImageRegion which properly contains our TextRegion should be
        # completely ignored, but an ImageRegion which is properly contained
        # in our TextRegion should be completely masked, while partial overlap
        # may be more difficult to decide. On the other hand, on the binary image,
        # we can use connected component analysis to mask foreground areas which
        # originate in the neighbouring regions. But that would introduce either
        # the assumption that the input has already been binarized, or a dependency
        # on some ad-hoc binarization method. Thus, it is preferable to use
        # a dedicated processor for this (which produces clipped AlternativeImage
        # or reduced polygon coordinates).
        if 'angle' in segment_xywh and segment_xywh['angle']:
            LOG.info("About to rotate segment '%s' by %.2f°",
                      segment.id, segment_xywh['angle'])
            segment_image = segment_image.rotate(segment_xywh['angle'],
                                                 expand=True,
                                                 #resample=Image.BILINEAR,
                                                 fillcolor='white')
    # subtract offset from any increase in binary region size over source:
    segment_xywh['x'] -= round(0.5 * max(0, segment_image.width  - segment_xywh['w']))
    segment_xywh['y'] -= round(0.5 * max(0, segment_image.height - segment_xywh['h']))
    return segment_image, segment_xywh

# to be refactored into core (as method of ocrd.workspace.Workspace):
def save_image_file(workspace, image,
                    file_id,
                    page_id=None,
                    file_grp='OCR-D-IMG', # or -BIN?
                    format='PNG',
                    force=True):
    """Store and reference an image as file into the workspace.
    
    Given a PIL.Image `image`, and an ID `file_id` to use in METS,
    store the image under the fileGrp `file_grp` and physical page
    `page_id` into the workspace (in a file name based on
    the `file_grp`, `file_id` and `format` extension).
    
    Return the (absolute) path of the created file.
    """
    image_bytes = io.BytesIO()
    image.save(image_bytes, format=format)
    file_path = os.path.join(file_grp,
                             file_id + '.' + format.lower())
    out = workspace.add_file(
        ID=file_id,
        file_grp=file_grp,
        pageId=page_id,
        local_filename=file_path,
        mimetype='image/' + format.lower(),
        content=image_bytes.getvalue(),
        force=force)
    LOG.info('created file ID: %s, file_grp: %s, path: %s',
             file_id, file_grp, out.local_filename)
    return file_path
