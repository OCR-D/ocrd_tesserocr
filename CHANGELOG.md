
Change Log
==========

Versioned according to [Semantic Versioning](http://semver.org/).

## Unreleased

## [0.2.2] - 2019-05-16

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
[0.1.3]: v0.1.3...v0.1.2
[0.1.2]: v0.1.2...v0.1.1
[0.1.1]: v0.1.1...v0.1.0
[0.1.0]: ../../compare/HEAD...v0.1.0
