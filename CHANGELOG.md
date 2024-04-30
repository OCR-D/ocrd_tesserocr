Change Log
==========

Versioned according to [Semantic Versioning](http://semver.org/).

## Unreleased

## [0.18.1] - 2024-03-07

Fixed:

  * Build, tests and documentation related to `make install-{tesserocr,tesseract}`, #200

## [0.18.0] - 2024-02-19

Changed:

  * `tesseract` and `tesserocr` included as submodules, installable via `make instal-tesser{act,ocr}`, #197
  * Updated docker setup accordingly, #197


## [0.17.0] - 2023-03-23

Fixed:

 * segment/recognize: fix `shrink_polygons`
 * segment/recognize: fix reinit scope (for `xpath_model` and `auto_model`)
 * CI: test multiple Python versions independent of ocrd/core image
 * CI: speed up build for EOL Python 3.6
 * CI: chmod o+w tessdata directory of PPA/OS Tesseract
 * deps-ubuntu: allow installation of PPA Tesseract to fail (for newer OS)

Changed:

 * adapted to Shapely v2
 * *: inherit from recognize (but override logger)
 * segment*: delegate constructor instead of wrapping instance
 * requires ocrd==2.48

## [0.16.0] - 2022-10-25

Changed:

  * require newer OCR-D/core to include OCR-D/core#934, #188
  * no more need to set `TESSDATA_PREFIX`
  * improved and up-to-date README

## [0.15.0] - 2022-10-23

Added:

  * binarize: `dpi` numerical parameter to specify pixel density, #186
  * binarize: `tiseg` boolean parameter to specify whether to call `tessapi.AnalyseLayout` for text-image separation, #186

Changed:

  * regonize: improved polygon handling, #186
  * resources: proper support for `moduledir`, companion to OCR-D/core#904, #187

## [0.14.0] - 2022-08-14

Changed:

  * list all resources in the ocrd-tool.json, #184, OCR-D/core#800
  * custom `--list-resources` handler, #176

## [0.13.6] - 2021-09-28

Fixed:

 * segment/recognize: no find_tables when already looking for cells

Changed:

 * segment/recognize: add param find_staves (for pageseg_apply_music_mask)
 * segment/recognize: :fire: set find_staves=false by default

## [0.13.5] - 2021-07-26

Fixed:

 * recognize: prevent invalid empty `Unicode` glyph choices

## [0.13.4] - 2021-07-20

Fixed:

  * recognize: only reset API when `xpath_model` or `auto_model` is active
  * recognize: for `glyph` level output, reduce choice confidence threshold
  * recognize: for `glyph` level output, skip choices with same text
  * recognize: avoid projecting empty text results from lower levels

Changed:

  * recognize: allow setting init-time (model-related) parameters

## [0.13.3] - 2021-07-01

Changed:

  * recognize: on glyph level, fall back to RIL.SYMBOL if ChoiceIterator is empty

## [0.13.2] - 2021-06-30

Fixed:

  * updated requirements

## [0.13.1] - 2021-06-30

Fixed:

  * deps-ubuntu/Docker: adapt to resmgr location mechanism, link to PPA models
  * recognize: :bug: skip detected segments if polygon cannot be made valid

Changed:

  * deskew: add line-level operation for script detection
  * recognize: query more choices for textequiv_level=glyph if available
  * recognize: :fire: reset Tesseract API when applying model/param settings per segment
  * recognize: :eyes: allow configuring Tesseract parameters per segment via XPath queries
  * recognize: :eyes: allow selecting recognition model per segment via XPath queries
  * recognize: :eyes: allow selecting recognition model automatically via confidence

## [0.13.0] - 2021-06-30

Changed:

  * segment*/recognize: annotate clipped,binarized AlternativeImage on page level
  * binarize: add page level, make default

## [0.12.0] - 2021-03-05

Changed:

  * resource lookup in a function to avoid module-level instantiation, #172
  * skip recognition of elements if they have `pc:TextEquiv` and `overwrite_text` is false-y, #170

Added:

  * New parameter `oem` to explicitly set the engine backend to use, #168, #170

## [0.11.0] - 2021-01-29

Changed:

  * Models are resolved via OCR-D/core resource manager default location (`$XDG_DATA_HOME`) or `$TESSDATA_PREFIX`, #166

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
[0.18.1]: ../../compare/v0.18.1...v0.18.0
[0.18.0]: ../../compare/v0.18.0...v0.17.0
[0.17.0]: ../../compare/v0.17.0...v0.16.0
[0.16.0]: ../../compare/v0.16.0...v0.15.0
[0.15.0]: ../../compare/v0.15.0...v0.14.0
[0.14.0]: ../../compare/v0.14.0...v0.13.6
[0.13.6]: ../../compare/v0.13.6...v0.13.5
[0.13.5]: ../../compare/v0.13.5...v0.13.4
[0.13.4]: ../../compare/v0.13.4...v0.13.3
[0.13.3]: ../../compare/v0.13.3...v0.13.2
[0.13.2]: ../../compare/v0.13.2...v0.13.1
[0.13.1]: ../../compare/v0.13.1...v0.13.0
[0.13.0]: ../../compare/v0.13.0...v0.12.0
[0.12.0]: ../../compare/v0.12.0...v0.11.0
[0.11.0]: ../../compare/v0.11.0...v0.10.1
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
