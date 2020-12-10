Change Log
==========

Versioned according to [Semantic Versioning](http://semver.org/).

## Unreleased

## [0.10.1] - 2020-12-10

Fixed:

 * segment*/recognize: reduce minimal region height to sane value
 * segment*/recognize: also disable text recognition if `model` is empty
 * segment-{region,line,word}: apply only single-level segmentation again
 * segment*/recognize: skip empty non-text blocks and all-reject words

Changed:

 * segment*/recognize: add option `shrink_polygons`, default to `false`
 * segment*/recognize: add Tesseract version to meta-data
 * recognize: add option `tesseract_parameters` to expose all variables

## [0.10.0] - 2020-12-01

Fixed:

 * when padding images, add the offset to coords of new segments
 * when segmenting regions, skip empty output coords more robustly
 * deskew/segment/recognize: skip empty input images more robustly
 * crop: fix pageId of new derived image
 * recognize: fix missing RIL for terminal `GetUTF8Text()`
 * recognize: fix `Confidence()` vs `MeanTextConf()`
 
Changed:

 * recognize: add all-in-one segmentation with flexible entry point
 * recognize: re-parameterize to `segmentation_level`+`textequiv_level`
 * recognize: :fire: rename `overwrite_words` to `overwrite_segments`
 * segment*: delegate to recognize
 * recognize: also annotate orientation and skew when segmenting regions
 * fontshape: new processor for TextStyle detection via pre-LSTM models
 * crop: also use existing text regions, if any
 * deskew: delegate to core for reflection and rotation
 * deskew: always get new image and set feature `deskewed` (even for 0°)

## [0.9.5] - 2020-10-02

Fixed:

 * logging according to https://github.com/OCR-D/core/pull/599 (again)

## [0.9.4] - 2020-09-24

Fixed:

 * recognize: be robust to different input image modes, Pillow#4925
 * logging according to https://github.com/OCR-D/core/pull/599

## [0.9.3] - 2020-09-15

Fixed:

 * segmentation: ensure new elements fit into their parent coords
 * segmentation: ensure valid coords

## [0.9.2] - 2020-09-04

Fixed:

 * segment-region: just ignore region outside of page frame, #145
 * deskew: add suffix to AlternativeImage file ID, #148

## [0.9.1] - 2020-08-16

Fixed:

 * crop: allow running on deskewed page, clip Border to original frame
 * deskew: refactoring artefact from #133, #142

## [0.9.0] - 2020-08-06

Changed:

  * All processors write to a single file group, #133
  * All processors set `pg:PcGts/pcGtsId` to `file_id` consistently, #136

## [0.8.5] - 2020-06-05

Fixed:

  * segment-region: ensure polygons are within page/Border

## [0.8.4] - 2020-06-05

Changed:

  * segment-region: in `sparse_text` mode, also add text lines

Fixed:

  * Always set path to `TESSDATA_PREFIX` for `tesserocr.get_languages`, #129

## [0.8.3] - 2020-05-12

Fixed:

  * recognize: ignore empty RO group

Changed:

  * recognize: add `padding` parameter

## [0.8.2] - 2020-04-08

Fixed:

  * segment-region: no empty (invalid) ReadingOrder when no regions
  * segment-region: add `sparse_text` mode choice
  * segment-line: make intersection with parent more robust
  * segment-table: use `SPARSE_TEXT` mode for cells
  
Changed:

  * Depend on OCR-D/core v2.4.4
  * Depend on sirfz/tesserocr v2.51

## [0.8.1] - 2020-02-17

Fixed:

  * recognize: fix buggy RTL behavior, glyph confidence defaults to 1, #112, #113

## [0.8.0] - 2020-01-24

Changed:

  * recognize: use lstm_choice_mode=2 for textequiv_level=glyph, #110
  * recognize: add char white/un/blacklisting parameters  enhancement, #109

Added:

  * all: add dpi parameter as manual override to image metadata  enhancement, #108

## [0.7.0] - 2020-01-23

Added:

  * segment-table: new processor that adds table cells as text regions, #104
  * `raw_lines` option, #104
  * interpret `overwrite_regions` more consistently, #104
  * annotate `@orientation` (independent of dedicated deskewing processor) for vertical and `@type` for all other text blocks, #104
  * no separators and noise regions in reading order, #104

Changed:

  * docker image built on Ubuntu 18.04, #94, #97
  * Consistent setup of docker, #97


## [0.6.0] - 2019-11-05

Changed:

  * Depend on OCR-D/core v2.0.0

## [0.5.1] - 2019-10-31

Fixed:

  * Correct version in ocrd-tool.json, #76

## [0.5.0] - 2019-10-26

  * Adapt to new core image API, #80
  * Use OCR core >= unstable 2.0.0a1

## [0.4.1] - 2019-10-29

  * Adapt to feature selection/filtering mechanism for derived images in core
  * Fixes for image-feature-related corner cases in crop and deskew
  * Use explicit (second) output fileGrp when producing derived images
  * Upgrade to upstream tesserocr 2.4.1
  * Use OCR core >= stable 1.0.0

## [0.4.0] - 2019-08-21

Changed:

  * :fire: `common.py` is now part of OCR-D/core's ocrd_utils, OCR-D/core#268, #49
  * many fixes and improvements to crop, deskew, binarize
  * proper handling of orientaton on page level
  * updated requirements


## [0.3.0] - 2019-06-28

Changed:
  * Use basename of input file for output name
  * Use .xml filename extension for PAGE output
  * Warn about existing border or regions in `crop`
  * Use `PSM.SPARSE_TEXT` without tables in `crop`
  * Filter unreliable regions in `crop`
  * Add padding around border in `crop`
  * Delete existing regions in `segment_region`
  * Cover vertical text and tables in `segment_region`
  * Add parameter `find_tables` in `segment_region`
  * Add parameter `crop_polygons` in `segment_region`
  * Add parameter `overwrite_regions` in `segment_region`
  * Add parameter `overwrite_lines` in `segment_line`
  * Add parameter `overwrite_words` in `segment_word`
  * Add page/region-level processor `deskew`
  * Add page/region/line-level processor `binarize`
  * Respect AlternativeImage on all levels

## [0.2.2] - 2019-05-20

Changed:

  * Add simple page cropping processor crop
  * Respect border cropping in segment_word
  * Add parameter overwrite_words in recognize
  * Make higher TextEquivs consistent after recognize
  
Fixed:

  * Remove invalid @externalRef from MetadataItem
  * Retain pageId in output (i.e. link to structMap)

## [0.2.1] - 2019-02-28

Fixed:

  * workspace.add_file was wrong in segment_word

## [0.2.0] - 2019-02-28

Changed:

  * Adapt to OCR-D/core 1.0.0b5 API

## [0.1.3] - 2019-01-04

Fixed:

  * Override locale to POSIX before importing tesserocr

Changed:

  * split recognizing existing glyphs vs. all in word

## [0.1.2] - 2018-09-03

Fixed:

  * arithmetic average (not product) for line conf, #22

## [0.1.1] - 2018-08-31

Fixed:

  * robust conf calculation (when no result), #21

## [0.1.0] - 2018-08-30

Changed:

  * Segment on all levels
  * Word and line confidences
  * Recognition with proper support for textequiv_level, drop `page` level

<!-- link-labels -->
[0.10.1]: ../../compare/v0.10.0...v0.10.1
[0.10.0]: ../../compare/v0.9.5...v0.10.0
[0.9.5]: ../../compare/v0.9.4...v0.9.5
[0.9.4]: ../../compare/v0.9.3...v0.9.4
[0.9.3]: ../../compare/v0.9.2...v0.9.3
[0.9.2]: ../../compare/v0.9.1...v0.9.2
[0.9.1]: ../../compare/v0.9.0...v0.9.1
[0.9.0]: ../../compare/v0.8.5...v0.9.0
[0.8.5]: ../../compare/v0.8.4...v0.8.5
[0.8.4]: ../../compare/v0.8.3...v0.8.4
[0.8.3]: ../../compare/v0.8.2...v0.8.3
[0.8.2]: ../../compare/v0.8.1...v0.8.2
[0.8.1]: ../../compare/v0.8.0...v0.8.1
[0.8.0]: ../../compare/v0.7.0...v0.8.0
[0.7.0]: ../../compare/v0.6.0...v0.7.0
[0.6.0]: ../../compare/v0.5.1...v0.6.0
[0.5.1]: ../../compare/v0.5.0...v0.5.1
[0.5.0]: ../../compare/v0.4.1...v0.5.0
[0.4.1]: ../../compare/v0.4.0...v0.4.1
[0.4.0]: ../../compare/v0.3.0...v0.4.0
[0.3.0]: ../../compare/v0.2.2...v0.3.0
[0.2.2]: ../../compare/v0.2.1...v0.2.2
[0.2.1]: ../../compare/v0.2.0...v0.2.1
[0.2.0]: ../../compare/v0.1.2...v0.2.0
[0.1.3]: ../../compare/v0.1.2...v0.1.3
[0.1.2]: ../../compare/v0.1.1...v0.1.2
[0.1.1]: ../../compare/v0.1.0...v0.1.1
[0.1.0]: ../../compare/HEAD...v0.1.0
