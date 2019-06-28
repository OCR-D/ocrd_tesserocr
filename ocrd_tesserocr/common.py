from __future__ import absolute_import

import os.path
import sys
import io

import numpy as np
from PIL import Image, ImageDraw

from ocrd_utils import getLogger, xywh_from_points, polygon_from_points

LOG = getLogger('') # to be refined by importer

# dummy (not available without ocrolib)
def resegment(mask_image, labels):
    return mask_image

# to be refactored into core (as function in ocrd_utils):
def polygon_mask(image, coordinates):
    mask = Image.new('L', image.size, 0)
    ImageDraw.Draw(mask).polygon(coordinates, outline=1, fill=255)
    return mask

# to be refactored into core (as function in ocrd_utils):
def rotate_polygon(coordinates, angle, orig={'x': 0, 'y': 0}):
    # if the region image has been rotated, we must also
    # rotate the coordinates of the line
    # (which relate to the top page image)
    # in the same direction but with inverse transformation
    # matrix (i.e. passive rotation), and
    # (since the region was rotated around its center,
    #  but our coordinates are now relative to the top left)
    # by first translating to center of region, then
    # rotating around that center, and translating back:
    # point := (point - region_center) * region_rotation + region_center
    # moreover, since rotation has reshaped/expanded the image,
    # the line coordinates must be offset by those additional pixels:
    # point := point + 0.5 * (new_region_size - old_region_size)
    angle = np.deg2rad(angle)
    # active rotation:  [[cos, -sin], [sin, cos]]
    # passive rotation: [[cos, sin], [-sin, cos]] (inverse)
    return [(orig['x']
             + (x - orig['x'])*np.cos(angle)
             + (y - orig['y'])*np.sin(angle),
             orig['y']
             - (x - orig['x'])*np.sin(angle)
             + (y - orig['y'])*np.cos(angle))
            for x, y in coordinates]

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
    
    When using AlternativeImage, if the resulting page image
    is larger than the annotated page, then pass down the page's
    box coordinates with an offset of half the width/height difference.
    
    Return the extracted image, and the page's box coordinates,
    relative to the source image (for passing down).
    """
    page_xywh = {'x': 0,
                 'y': 0,
                 'w': page_image.width,
                 'h': page_image.height}
    # FIXME: remove PrintSpace here as soon as GT abides by the PAGE standard:
    border = page.get_Border() or page.get_PrintSpace()
    if border and border.get_Coords():
        LOG.debug("Using explictly set page border '%s' for page '%s'",
                  border.get_Coords().points, page_id)
        page_xywh = xywh_from_points(border.get_Coords().points)
    
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
        page_image = page_image.crop(
            box=(page_xywh['x'],
                 page_xywh['y'],
                 page_xywh['x'] + page_xywh['w'],
                 page_xywh['y'] + page_xywh['h']))
        # FIXME: mask away all GraphicRegion, SeparatorRegion etc which
        # could overlay any text regions
    # subtract offset from any increase in binary region size over source:
    page_xywh['x'] -= 0.5 * max(0, page_image.width  - page_xywh['w'])
    page_xywh['y'] -= 0.5 * max(0, page_image.height - page_xywh['h'])
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
    
    When cropping, respect any angle annotated for the region
    (from deskewing) by rotating the cropped image, respectively.
    Regardless, if the resulting region image is larger than
    the annotated region, pass down the region's box coordinates
    with an offset of half the width/height difference.
    
    Return the extracted image, and the region's box coordinates,
    relative to the page image (for passing down).
    """
    region_xywh = xywh_from_points(region.get_Coords().points)
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
        region_image = page_image.crop(
            box=(region_xywh['x'] - page_xywh['x'],
                 region_xywh['y'] - page_xywh['y'],
                 region_xywh['x'] - page_xywh['x'] + region_xywh['w'],
                 region_xywh['y'] - page_xywh['y'] + region_xywh['h']))
        # FIXME: mask any overlapping regions (esp. Separator/Noise/Image)
        # but we might need overlapping rules: e.g. an ImageRegion which
        # properly contains our TextRegion should be completely ignored, but
        # an ImageRegion which is properly contained in our TextRegion should
        # be completely masked, while partial overlap may be more difficult
        # to decide (use polygons?)
        if region_xywh['angle']:
            LOG.info("About to rotate region '%s' by %.2f°",
                      region.id, region_xywh['angle'])
            region_image = region_image.rotate(region_xywh['angle'],
                                               expand=True,
                                               #resample=Image.BILINEAR,
                                               fillcolor='white')
    # subtract offset from any increase in binary region size over source:
    region_xywh['x'] -= 0.5 * max(0, region_image.width  - region_xywh['w'])
    region_xywh['y'] -= 0.5 * max(0, region_image.height - region_xywh['h'])
    return region_image, region_xywh

# to be refactored into core (as method of ocrd.workspace.Workspace):
def image_from_line(workspace, line,
                    region_image, region_xywh,
                    segmentation=None):
    """Extract the TextLine image from a TextRegion image.
    
    Given a PIL.Image of the region, `region_image`,
    and its coordinates relative to the page, `region_xywh`,
    and a TextLine object logically contained in it, `line`,
    extract its PIL.Image from AlternativeImage (if it exists),
    or via cropping from `region_image`.
    
    When cropping, respect any angle annotated for the region
    (from deskewing) by compensating the line coordinates in
    an inverse transformation (translation to center, rotation,
    re-translation). Also, mind the difference between annotated
    and actual size of the region (usually from deskewing), by
    a respective offset into the image. Cropping uses a polygon
    mask (not just the rectangle).
    
    If passed an optional labelling for the region, `segmentation`,
    the mask is shrinked further to the largest overlapping line
    label, which avoids seeing ascenders from lines below, and
    descenders from lines above `line`.
    
    If the resulting line image is larger than the annotated line,
    pass down the line's box coordinates with an offset of half
    the width/height difference.
    
    Return the extracted image, and the line's box coordinates,
    relative to the region image (for passing down).
    """
    line_points = line.get_Coords().points
    line_xywh = xywh_from_points(line_points)
    line_polygon = [(x - region_xywh['x'],
                     y - region_xywh['y'])
                    for x, y in polygon_from_points(line_points)]
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
        line_polygon = rotate_polygon(line_polygon,
                                      region_xywh['angle'],
                                      orig={'x': 0.5 * region_image.width,
                                            'y': 0.5 * region_image.height})
        line_mask = polygon_mask(region_image, line_polygon)
        if isinstance(segmentation, np.ndarray):
            # modify mask from (ad-hoc) line segmentation of region
            # (shrink to largest label spread in that area):
            line_mask = resegment(line_mask, segmentation)
        # create a background image from its median color
        # (in case it has not been binarized yet):
        region_array = np.asarray(region_image)
        background = np.median(region_array, axis=[0, 1], keepdims=True)
        region_array = np.broadcast_to(background.astype(np.uint8), region_array.shape)
        line_image = Image.fromarray(region_array)
        line_image.paste(region_image, mask=line_mask)
        # recrop into a line:
        bbox = line_mask.getbbox()
        if bbox:
            left, upper, right, lower = bbox
            # keep upper/lower, regardless of h (no vertical padding)
            # pad left/right if target width w is larger:
            margin_x = (line_xywh['w'] - right + left) // 2
            left = max(0, left - margin_x)
            right = min(line_mask.width, left + line_xywh['w'])
        else:
            left = line_xywh['x'] - region_xywh['x']
            upper = line_xywh['y'] - region_xywh['y']
            right = left + line_xywh['w']
            lower = upper + line_xywh['h']
        line_image = line_image.crop(box=(left, upper, right, lower))
    # subtract offset from any increase in binary line size over source:
    line_xywh['x'] -= 0.5 * max(0, line_image.width  - line_xywh['w'])
    line_xywh['y'] -= 0.5 * max(0, line_image.height - line_xywh['h'])
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
    word_points = word.get_Coords().points
    word_xywh = xywh_from_points(word_points)
    word_polygon = [(x - line_xywh['x'],
                     y - line_xywh['y'])
                    for x, y in polygon_from_points(word_points)]
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
        word_mask = polygon_mask(line_image, word_polygon)
        # create a background image from its median color
        # (in case it has not been binarized yet):
        line_array = np.asarray(line_image)
        background = np.median(line_array, axis=[0, 1], keepdims=True)
        line_array = np.broadcast_to(background.astype(np.uint8), line_array.shape)
        word_image = Image.fromarray(line_array)
        word_image.paste(line_image, mask=word_mask)
        # recrop into a line:
        bbox = word_mask.getbbox()
        if bbox:
            left, upper, right, lower = bbox
            # keep upper/lower, regardless of h (no vertical padding)
            # pad left/right if target width w is larger:
            margin_x = (word_xywh['w'] - right + left) // 2
            left = max(0, left - margin_x)
            right = min(word_mask.width, left + word_xywh['w'])
        else:
            left = word_xywh['x'] - line_xywh['x']
            upper = word_xywh['y'] - line_xywh['y']
            right = left + word_xywh['w']
            lower = upper + word_xywh['h']
        word_image = word_image.crop(box=(left, upper, right, lower))
    # subtract offset from any increase in binary line size over source:
    word_xywh['x'] -= 0.5 * max(0, word_image.width  - word_xywh['w'])
    word_xywh['y'] -= 0.5 * max(0, word_image.height - word_xywh['h'])
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
    glyph_points = glyph.get_Coords().points
    glyph_xywh = xywh_from_points(glyph_points)
    glyph_polygon = [(x - word_xywh['x'],
                      y - word_xywh['y'])
                     for x, y in polygon_from_points(glyph_points)]
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
        glyph_mask = polygon_mask(word_image, glyph_polygon)
        # create a background image from its median color
        # (in case it has not been binarized yet):
        word_array = np.asarray(word_image)
        background = np.median(word_array, axis=[0, 1], keepdims=True)
        word_array = np.broadcast_to(background.astype(np.uint8), word_array.shape)
        glyph_image = Image.fromarray(word_array)
        glyph_image.paste(word_image, mask=glyph_mask)
        # recrop into a word:
        bbox = glyph_mask.getbbox()
        if bbox:
            left, upper, right, lower = bbox
            # keep upper/lower, regardless of h (no vertical padding)
            # pad left/right if target width w is larger:
            margin_x = (glyph_xywh['w'] - right + left) // 2
            left = max(0, left - margin_x)
            right = min(glyph_mask.width, left + glyph_xywh['w'])
        else:
            left = glyph_xywh['x'] - word_xywh['x']
            upper = glyph_xywh['y'] - word_xywh['y']
            right = left + glyph_xywh['w']
            lower = upper + glyph_xywh['h']
        glyph_image = glyph_image.crop(box=(left, upper, right, lower))
    # subtract offset from any increase in binary word size over source:
    glyph_xywh['x'] -= 0.5 * max(0, glyph_image.width  - glyph_xywh['w'])
    glyph_xywh['y'] -= 0.5 * max(0, glyph_image.height - glyph_xywh['h'])
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
    """Constructs a numeric list representing a bounding box from polygon coordinates in page representation."""
    xys = [[int(p) for p in pair.split(',')] for pair in points.split(' ')]
    minx = sys.maxsize
    miny = sys.maxsize
    maxx = 0
    maxy = 0
    for xy in xys:
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
def points_from_bbox(minx, miny, maxx, maxy):
    """Constructs polygon coordinates in page representation from a numeric list representing a bounding box."""
    return "%i,%i %i,%i %i,%i %i,%i" % (
        minx, miny, maxx, miny, maxx, maxy, minx, maxy)

# to be refactored into core (as function in ocrd_utils):
def xywh_from_bbox(minx, miny, maxx, maxy):
    """Converts a bounding box from a numeric list to a numeric dict representation."""
    return {
        'x': minx,
        'y': miny,
        'w': maxx - minx,
        'h': maxy - miny,
    }

# to be refactored into core (as function in ocrd_utils):
def bbox_from_xywh(xywh):
    """Converts a bounding box from a numeric dict to a numeric list representation."""
    return (
        xywh['x'],
        xywh['y'],
        xywh['x'] + xywh['w'],
        xywh['y'] + xywh['h']
    )

# to be refactored into core (as function in ocrd_utils):
def points_from_polygon(polygon):
    """Converts polygon coordinates from a numeric list representation to a page representation."""
    return " ".join("%i,%i" % (x, y) for x, y in polygon)

def membername(class_, val):
    return next((k for k, v in class_.__dict__.items() if v == val), str(val))
