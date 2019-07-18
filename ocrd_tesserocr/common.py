from __future__ import absolute_import

import os.path
import sys
import io

import numpy as np
from PIL import Image, ImageDraw, ImageStat

from ocrd_utils import getLogger, xywh_from_points, polygon_from_points

LOG = getLogger('') # to be refined by importer

# to be refactored into core (as function in ocrd_utils):
def polygon_mask(image, coordinates):
    """"Create a mask image of a polygon.
    
    Given a PIL.Image `image` (merely for dimensions), and
    a numpy array `polygon` of relative coordinates into the image,
    create a new image of the same size with black background, and
    fill everything inside the polygon hull with white.
    
    Return the new PIL.Image.
    """
    mask = Image.new('L', image.size, 0)
    if isinstance(coordinates, np.ndarray):
        coordinates = list(map(tuple, coordinates))
    ImageDraw.Draw(mask).polygon(coordinates, outline=1, fill=255)
    return mask

# to be refactored into core (as function in ocrd_utils):
def image_from_polygon(image, polygon):
    """"Mask an image with a polygon.
    
    Given a PIL.Image `image` and a numpy array `polygon`
    of relative coordinates into the image, put everything
    outside the polygon hull to the background. Since `image`
    is not necessarily binarized yet, determine the background
    from the median color (instead of white).
    
    Return a new PIL.Image.
    """
    mask = polygon_mask(image, polygon)
    # create a background image from its median color
    # (in case it has not been binarized yet):
    # array = np.asarray(image)
    # background = np.median(array, axis=[0, 1], keepdims=True)
    # array = np.broadcast_to(background.astype(np.uint8), array.shape)
    background = ImageStat.Stat(image).median[0]
    new_image = Image.new('L', image.size, background)
    new_image.paste(image, mask=mask)
    return new_image

# to be refactored into core (as function in ocrd_utils):
def crop_image(image, box=None):
    """"Crop an image to a rectangle, filling with background.
    
    Given a PIL.Image `image` and a list `box` of the bounding
    rectangle relative to the image, crop at the box coordinates,
    filling everything outside `image` with the background.
    (This covers the case where `box` indexes are negative or
    larger than `image` width/height. PIL.Image.crop would fill
    with black.) Since `image` is not necessarily binarized yet,
    determine the background from the median color (instead of
    white).
    
    Return a new PIL.Image.
    """
    # todo: perhaps we should issue a warning if we encounter this
    # (It should be invalid in PAGE-XML to extend beyond parents.)
    if not box:
        box = (0, 0, image.width, image.height)
    xywh = xywh_from_bbox(*box)
    background = ImageStat.Stat(image).median[0]
    new_image = Image.new(image.mode, (xywh['w'], xywh['h']),
                          background) # or 'white'
    new_image.paste(image, (-xywh['x'], -xywh['y']))
    return new_image

# to be refactored into core (as function in ocrd_utils):
def rotate_coordinates(polygon, angle, orig=np.array([0, 0])):
    """Apply a passive rotation transformation to the given coordinates.
    
    Given a numpy array `polygon` of points and a rotation `angle`,
    as well as a numpy array `orig` of the center of rotation,
    calculate the coordinate transform corresponding to the rotation
    of the underlying image by `angle` degrees at `center` by
    applying translation to the center, inverse rotation,
    and translation from the center.

    Return a numpy array of the resulting polygon.
    """
    angle = np.deg2rad(angle)
    cos = np.cos(angle)
    sin = np.sin(angle)
    # active rotation:  [[cos, -sin], [sin, cos]]
    # passive rotation: [[cos, sin], [-sin, cos]] (inverse)
    return orig + np.dot(polygon - orig, np.array([[cos, sin], [-sin, cos]]).transpose())

# to be refactored into core (as method of ocrd.workspace.Workspace):
def coordinates_of_segment(segment, parent_image, parent_xywh):
    """Extract the relative coordinates polygon of a PAGE segment element.
    
    Given a Region / TextLine / Word / Glyph `segment` and
    the PIL.Image of its parent Page / Region / TextLine / Word
    along with its bounding box, calculate the relative coordinates
    of the segment within the image. That is, shift all points from
    the offset of the parent, and (in case the parent was rotated,)
    rotate all points with the center of the image as origin.
    
    Return the rounded numpy array of the resulting polygon.
    """
    # get polygon:
    polygon = np.array(polygon_from_points(segment.get_Coords().points))
    # offset correction (shift coordinates to base of segment):
    polygon -= np.array([parent_xywh['x'], parent_xywh['y']])
    # angle correction (rotate coordinates if image has been rotated):
    if 'angle' in parent_xywh:
        polygon = rotate_coordinates(
            polygon, parent_xywh['angle'],
            orig=np.array([0.5 * parent_image.width,
                           0.5 * parent_image.height]))
    return np.round(polygon).astype(np.int32)

# to be refactored into core (as method of ocrd.workspace.Workspace):
def coordinates_for_segment(polygon, parent_image, parent_xywh):
    """Convert a relative coordinates polygon to absolute.
    
    Given a numpy array `polygon` of points, and a parent PIL.Image
    along with its bounding box to which the coordinates are relative,
    calculate the absolute coordinates within the page.
    That is, (in case the parent was rotated,) rotate all points in
    opposite direction with the center of the image as origin, then
    shift all points to the offset of the parent.
    
    Return the rounded numpy array of the resulting polygon.
    """
    # angle correction (unrotate coordinates if image has been rotated):
    if 'angle' in parent_xywh:
        polygon = rotate_coordinates(
            polygon, -parent_xywh['angle'],
            orig=np.array([0.5 * parent_image.width,
                           0.5 * parent_image.height]))
    # offset correction (shift coordinates from base of segment):
    polygon += np.array([parent_xywh['x'], parent_xywh['y']])
    return np.round(polygon).astype(np.uint32)

# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_page(workspace, page,
                    page_image,
                    page_id):
    """Extract the Page image from the workspace.
    
    Given a PIL.Image of the page, `page_image`,
    and the Page object logically associated with it, `page`,
    extract its PIL.Image from AlternativeImage (if it exists),
    or via cropping from `page_image` (if a Border exists),
    or by just returning `page_image` (otherwise).
    
    When cropping, respect any orientation angle annotated for
    the page (from page-level deskewing) by rotating the
    cropped image, respectively.
    
    If the resulting page image is larger than the annotated page,
    pass down the page's box coordinates with an offset of half
    the width/height difference.
    
    Return the extracted image, and the page's box coordinates,
    relative to the source image (for passing down).
    """
    page_xywh = {'x': 0,
                 'y': 0,
                 'w': page_image.width,
                 'h': page_image.height}
    # FIXME: uncomment as soon as we get @orientation in PageType:
    # # region angle: PAGE orientation is defined clockwise,
    # # whereas PIL/ndimage rotation is in mathematical direction:
    # page_xywh['angle'] = -(page.get_orientation() or 0)
    # FIXME: remove PrintSpace here as soon as GT abides by the PAGE standard:
    border = page.get_Border() or page.get_PrintSpace()
    if border:
        page_points = border.get_Coords().points
        LOG.debug("Using explictly set page border '%s' for page '%s'",
                  page_points, page_id)
        page_xywh = xywh_from_points(page_points)
        page_polygon = np.array(polygon_from_points(page_points))
    
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
        # create a mask from the page polygon:
        page_image = image_from_polygon(page_image, page_polygon)
        # recrop into page rectangle:
        page_image = crop_image(page_image,
            box=(page_xywh['x'],
                 page_xywh['y'],
                 page_xywh['x'] + page_xywh['w'],
                 page_xywh['y'] + page_xywh['h']))
        # FIXME: uncomment as soon as we get @orientation in PageType:
        # if page_xywh['angle']:
        #     LOG.info("About to rotate page '%s' by %.2f°",
        #               page_id, page_xywh['angle'])
        #     page_image = page_image.rotate(page_xywh['angle'],
        #                                        expand=True,
        #                                        #resample=Image.BILINEAR,
        #                                        fillcolor='white')
    # subtract offset from any increase in binary region size over source:
    page_xywh['x'] -= round(0.5 * max(0, page_image.width  - page_xywh['w']))
    page_xywh['y'] -= round(0.5 * max(0, page_image.height - page_xywh['h']))
    return page_image, page_xywh

# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_region(workspace, region,
                      page_image, page_xywh):
    """Extract the TextRegion image from a Page image.
    
    Given a PIL.Image of the page, `page_image`,
    and its coordinates relative to the border, `page_xywh`,
    and a TextRegion object logically contained in it, `region`,
    extract its PIL.Image from AlternativeImage (if it exists),
    or via cropping from `page_image`.
    
    When cropping, respect any orientation angle annotated for
    the page (from page-level deskewing) by compensating the
    region coordinates in an inverse transformation (translation
    to center, rotation, re-translation).
    Also, mind the difference between annotated and actual size
    of the page (usually from deskewing), by a respective offset
    into the image. Cropping uses a polygon mask (not just the
    rectangle).
    
    When cropping, respect any orientation angle annotated for
    the region (from region-level deskewing) by rotating the
    cropped image, respectively.

    If the resulting region image is larger than the annotated region,
    pass down the region's box coordinates with an offset of half
    the width/height difference.
    
    Return the extracted image, and the region's box coordinates,
    relative to the page image (for passing down).
    """
    region_xywh = xywh_from_points(region.get_Coords().points)
    region_polygon = coordinates_of_segment(region, page_image, page_xywh)
    # region angle: PAGE orientation is defined clockwise,
    # whereas PIL/ndimage rotation is in mathematical direction:
    region_xywh['angle'] = -(region.get_orientation() or 0)
    alternative_image = region.get_AlternativeImage()
    if alternative_image:
        # (e.g. from region-level cropping, binarization, deskewing or despeckling)
        LOG.debug("Using AlternativeImage %d (%s) for region '%s'",
                  len(alternative_image), alternative_image[-1].get_comments(),
                  region.id)
        region_image = workspace.resolve_image_as_pil(
            alternative_image[-1].get_filename())
    else:
        # create a mask from the region polygon:
        region_image = image_from_polygon(page_image, region_polygon)
        # recrop into region rectangle:
        region_image = crop_image(region_image,
            box=(region_xywh['x'] - page_xywh['x'],
                 region_xywh['y'] - page_xywh['y'],
                 region_xywh['x'] - page_xywh['x'] + region_xywh['w'],
                 region_xywh['y'] - page_xywh['y'] + region_xywh['h']))
        # note: We should mask overlapping neighbouring regions here
        # (especially Separator/Noise/GraphicRegion, but also TextRegion),
        # but finding the right clipping rules can be difficult if operating
        # on the raw (non-binary) image data alone: e.g. an ImageRegion which
        # properly contains our TextRegion should be completely ignored, but
        # an ImageRegion which is properly contained in our TextRegion should
        # be completely masked, while partial overlap may be more difficult
        # to decide. On the other hand, on the binary image, we can use
        # connected component analysis to mask foreground areas which originate
        # in the neighbouring regions. But that would introduce either the
        # assumption that the input has already been binarized, or a dependency
        # on some ad-hoc binarization method. Thus, it is preferable to use
        # a dedicated processor for this (which produces clipped AlternativeImage
        # or reduced polygon coordinates).
        if region_xywh['angle']:
            LOG.info("About to rotate region '%s' by %.2f°",
                      region.id, region_xywh['angle'])
            region_image = region_image.rotate(region_xywh['angle'],
                                               expand=True,
                                               #resample=Image.BILINEAR,
                                               fillcolor='white')
    # subtract offset from any increase in binary region size over source:
    region_xywh['x'] -= round(0.5 * max(0, region_image.width  - region_xywh['w']))
    region_xywh['y'] -= round(0.5 * max(0, region_image.height - region_xywh['h']))
    return region_image, region_xywh

# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_line(workspace, line,
                    region_image, region_xywh):
    """Extract the TextLine image from a TextRegion image.
    
    Given a PIL.Image of the region, `region_image`,
    and its coordinates relative to the page, `region_xywh`,
    and a TextLine object logically contained in it, `line`,
    extract its PIL.Image from AlternativeImage (if it exists),
    or via cropping from `region_image`.
    
    When cropping, respect any orientation angle annotated for
    the region (from region-level deskewing) by compensating the
    line coordinates in an inverse transformation (translation
    to center, rotation, re-translation).
    Also, mind the difference between annotated and actual size
    of the region (usually from deskewing), by a respective offset
    into the image. Cropping uses a polygon mask (not just the
    rectangle).
    
    If the resulting line image is larger than the annotated line,
    pass down the line's box coordinates with an offset of half
    the width/height difference.
    
    Return the extracted image, and the line's box coordinates,
    relative to the region image (for passing down).
    """
    line_xywh = xywh_from_points(line.get_Coords().points)
    line_polygon = coordinates_of_segment(line, region_image, region_xywh)
    alternative_image = line.get_AlternativeImage()
    if alternative_image:
        # (e.g. from line-level cropping, deskewing or despeckling)
        LOG.debug("Using AlternativeImage %d (%s) for line '%s'",
                  len(alternative_image), alternative_image[-1].get_comments(),
                  line.id)
        line_image = workspace.resolve_image_as_pil(
            alternative_image[-1].get_filename())
    else:
        # create a mask from the line polygon:
        line_image = image_from_polygon(region_image, line_polygon)
        # recrop into line rectangle:
        line_image = crop_image(line_image,
            box=(line_xywh['x'] - region_xywh['x'],
                 line_xywh['y'] - region_xywh['y'],
                 line_xywh['x'] - region_xywh['x'] + line_xywh['w'],
                 line_xywh['y'] - region_xywh['y'] + line_xywh['h']))
        # note: We should mask overlapping neighbouring lines here,
        # but finding the right clipping rules can be difficult if operating
        # on the raw (non-binary) image data alone: for each intersection, it
        # must be decided which one of either textline to assign. On the other
        # hand, on the binary image, we can use connected component analysis
        # to mask foreground areas which originate in the neighbouring regions.
        # But that would introduce either the assumption that the input has
        # already been binarized, or a dependency on some ad-hoc binarization
        # method. Thus, it is preferable to use a dedicated processor for this
        # (which produces clipped AlternativeImage or reduced polygon coordinates).
    # subtract offset from any increase in binary line size over source:
    line_xywh['x'] -= round(0.5 * max(0, line_image.width  - line_xywh['w']))
    line_xywh['y'] -= round(0.5 * max(0, line_image.height - line_xywh['h']))
    return line_image, line_xywh
                
# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_word(workspace, word,
                    line_image, line_xywh):
    """Extract the Word image from a TextLine image.
    
    Given a PIL.Image of the line, `line_image`,
    and its coordinates relative to the region, `line_xywh`,
    and a Word object logically contained in it, `word`,
    extract its PIL.Image from AlternativeImage (if it exists),
    or via cropping from `line_image`.
    
    When cropping, mind the difference between annotated
    and actual size of the line (usually from deskewing), by
    a respective offset into the image. Cropping uses a polygon
    mask (not just the rectangle).
    
    If the resulting word image is larger than the annotated word,
    pass down the word's box coordinates with an offset of half
    the width/height difference.
    
    Return the extracted image, and the word's box coordinates,
    relative to the line image (for passing down).
    """
    word_xywh = xywh_from_points(word.get_Coords().points)
    word_polygon = coordinates_of_segment(word, line_image, line_xywh)
    alternative_image = word.get_AlternativeImage()
    if alternative_image:
        # (e.g. from word-level cropping or binarization)
        LOG.debug("Using AlternativeImage %d (%s) for word '%s'",
                  len(alternative_image), alternative_image[-1].get_comments(),
                  word.id)
        word_image = workspace.resolve_image_as_pil(
            alternative_image[-1].get_filename())
    else:
        # create a mask from the word polygon:
        word_image = image_from_polygon(line_image, word_polygon)
        # recrop into word rectangle:
        word_image = crop_image(word_image,
            box=(word_xywh['x'] - line_xywh['x'],
                 word_xywh['y'] - line_xywh['y'],
                 word_xywh['x'] - line_xywh['x'] + word_xywh['w'],
                 word_xywh['y'] - line_xywh['y'] + word_xywh['h']))
    # subtract offset from any increase in binary line size over source:
    word_xywh['x'] -= round(0.5 * max(0, word_image.width  - word_xywh['w']))
    word_xywh['y'] -= round(0.5 * max(0, word_image.height - word_xywh['h']))
    return word_image, word_xywh

# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_glyph(workspace, glyph,
                    word_image, word_xywh):
    """Extract the Glyph image from a Word image.
    
    Given a PIL.Image of the word, `word_image`,
    and its coordinates relative to the line, `word_xywh`,
    and a Glyph object logically contained in it, `glyph`,
    extract its PIL.Image from AlternativeImage (if it exists),
    or via cropping from `word_image`.
    
    When cropping, mind the difference between annotated
    and actual size of the word (usually from deskewing), by
    a respective offset into the image. Cropping uses a polygon
    mask (not just the rectangle).
    
    If the resulting glyph image is larger than the annotated glyph,
    pass down the glyph's box coordinates with an offset of half
    the width/height difference.
    
    Return the extracted image, and the glyph's box coordinates,
    relative to the word image (for passing down).
    """
    glyph_xywh = xywh_from_points(glyph.get_Coords().points)
    glyph_polygon = coordinates_of_segment(glyph, word_image, word_xywh)
    alternative_image = glyph.get_AlternativeImage()
    if alternative_image:
        # (e.g. from glyph-level cropping or binarization)
        LOG.debug("Using AlternativeImage %d (%s) for glyph '%s'",
                  len(alternative_image), alternative_image[-1].get_comments(),
                  glyph.id)
        glyph_image = workspace.resolve_image_as_pil(
            alternative_image[-1].get_filename())
    else:
        # create a mask from the glyph polygon:
        glyph_image = image_from_polygon(word_image, glyph_polygon)
        # recrop into glyph rectangle:
        glyph_image = crop_image(glyph_image,
            box=(glyph_xywh['x'] - word_xywh['x'],
                 glyph_xywh['y'] - word_xywh['y'],
                 glyph_xywh['x'] - word_xywh['x'] + glyph_xywh['w'],
                 glyph_xywh['y'] - word_xywh['y'] + glyph_xywh['h']))
    # subtract offset from any increase in binary word size over source:
    glyph_xywh['x'] -= round(0.5 * max(0, glyph_image.width  - glyph_xywh['w']))
    glyph_xywh['y'] -= round(0.5 * max(0, glyph_image.height - glyph_xywh['h']))
    return glyph_image, glyph_xywh

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

# to be refactored into core (as function in ocrd_utils):
def bbox_from_points(points):
    """Construct a numeric list representing a bounding box from polygon coordinates in page representation."""
    xys = [[int(p) for p in pair.split(',')] for pair in points.split(' ')]
    return bbox_from_polygon(xys)

# to be refactored into core (as function in ocrd_utils):
def points_from_bbox(minx, miny, maxx, maxy):
    """Construct polygon coordinates in page representation from a numeric list representing a bounding box."""
    return "%i,%i %i,%i %i,%i %i,%i" % (
        minx, miny, maxx, miny, maxx, maxy, minx, maxy)

# to be refactored into core (as function in ocrd_utils):
def xywh_from_bbox(minx, miny, maxx, maxy):
    """Convert a bounding box from a numeric list to a numeric dict representation."""
    return {
        'x': minx,
        'y': miny,
        'w': maxx - minx,
        'h': maxy - miny,
    }

# to be refactored into core (as function in ocrd_utils):
def bbox_from_xywh(xywh):
    """Convert a bounding box from a numeric dict to a numeric list representation."""
    return (
        xywh['x'],
        xywh['y'],
        xywh['x'] + xywh['w'],
        xywh['y'] + xywh['h']
    )

# to be refactored into core (as function in ocrd_utils):
def points_from_polygon(polygon):
    """Convert polygon coordinates from a numeric list representation to a page representation."""
    return " ".join("%i,%i" % (x, y) for x, y in polygon)

# to be refactored into core (as function in ocrd_utils):
def xywh_from_polygon(polygon):
    """Construct a numeric dict representing a bounding box from polygon coordinates in numeric list representation."""
    return xywh_from_bbox(*bbox_from_polygon(polygon))

# to be refactored into core (as function in ocrd_utils):
def polygon_from_xywh(xywh):
    """Construct polygon coordinates in numeric list representation from numeric dict representing a bounding box."""
    return polygon_from_bbox(*bbox_from_xywh(xywh))

# to be refactored into core (as function in ocrd_utils):
def bbox_from_polygon(polygon):
    """Construct a numeric list representing a bounding box from polygon coordinates in numeric list representation."""
    minx = sys.maxsize
    miny = sys.maxsize
    maxx = 0
    maxy = 0
    for xy in polygon:
        if xy[0] < minx:
            minx = xy[0]
        if xy[0] > maxx:
            maxx = xy[0]
        if xy[1] < miny:
            miny = xy[1]
        if xy[1] > maxy:
            maxy = xy[1]
    return minx, miny, maxx, maxy

# to be refactored into core (as function in ocrd_utils):
def polygon_from_bbox(minx, miny, maxx, maxy):
    """Construct polygon coordinates in numeric list representation from a numeric list representing a bounding box."""
    return [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy]]

# to be refactored into core (as function in ocrd_utils):
def polygon_from_x0y0x1y1(x0y0x1y1):
    """Construct polygon coordinates in numeric list representation from a string list representing a bounding box."""
    minx = int(x0y0x1y1[0])
    miny = int(x0y0x1y1[1])
    maxx = int(x0y0x1y1[2])
    maxy = int(x0y0x1y1[3])
    return [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy]]

def membername(class_, val):
    """Convert a member variable/constant into a member name string."""
    return next((k for k, v in class_.__dict__.items() if v == val), str(val))
