import click

from ocrd.decorators import ocrd_cli_options, ocrd_cli_wrap_processor
from ocrd_tesserocr.recognize import TesserocrRecognize
from ocrd_tesserocr.segment_region import TesserocrSegmentRegion
from ocrd_tesserocr.segment_line import TesserocrSegmentLine
from ocrd_tesserocr.segment_word import TesserocrSegmentWord

@click.command()
@ocrd_cli_options
def ocrd_tesserocr_segment_region(*args, **kwargs):
    return ocrd_cli_wrap_processor(TesserocrSegmentRegion, *args, **kwargs)

@click.command()
@ocrd_cli_options
def ocrd_tesserocr_segment_line(*args, **kwargs):
    return ocrd_cli_wrap_processor(TesserocrSegmentLine, *args, **kwargs)

@click.command()
@ocrd_cli_options
def ocrd_tesserocr_segment_word(*args, **kwargs):
    return ocrd_cli_wrap_processor(TesserocrSegmentWord, *args, **kwargs)

@click.command()
@ocrd_cli_options
def ocrd_tesserocr_recognize(*args, **kwargs):
    return ocrd_cli_wrap_processor(TesserocrRecognize, *args, **kwargs)
