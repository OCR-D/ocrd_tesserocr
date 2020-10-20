# -*- coding: utf-8 -*-
"""
Installs the following command-line executables:

    - ocrd-tesserocr-binarize
    - ocrd-tesserocr-crop
    - ocrd-tesserocr-deskew
    - ocrd-tesserocr-recognize
    - ocrd-tesserocr-segment
    - ocrd-tesserocr-segment-region
    - ocrd-tesserocr-segment-table
    - ocrd-tesserocr-segment-line
    - ocrd-tesserocr-segment-word
    - ocrd-tesserocr-fontshape
"""
import codecs
import json
from setuptools import setup, find_packages

with open('./ocrd-tool.json', 'r') as f:
    version = json.load(f)['version']

setup(
    name='ocrd_tesserocr',
    version=version,
    description='wrap Tesseract preprocessing, segmentation and recognition',
    long_description=codecs.open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author='Konstantin Baierer, Kay-Michael Würzner, Robert Sachunsky',
    author_email='unixprog@gmail.com, wuerzner@gmail.com, sachunsky@informatik.uni-leipzig.de',
    url='https://github.com/OCR-D/ocrd_tesserocr',
    license='Apache License 2.0',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=open('requirements.txt').read().split('\n'),
    package_data={
        '': ['*.json', '*.yml', '*.yaml'],
    },
    entry_points={
        'console_scripts': [
            'ocrd-tesserocr-fontshape=ocrd_tesserocr.cli:ocrd_tesserocr_fontshape',
            'ocrd-tesserocr-recognize=ocrd_tesserocr.cli:ocrd_tesserocr_recognize',
            'ocrd-tesserocr-segment=ocrd_tesserocr.cli:ocrd_tesserocr_segment',
            'ocrd-tesserocr-segment-region=ocrd_tesserocr.cli:ocrd_tesserocr_segment_region',
            'ocrd-tesserocr-segment-table=ocrd_tesserocr.cli:ocrd_tesserocr_segment_table',
            'ocrd-tesserocr-segment-line=ocrd_tesserocr.cli:ocrd_tesserocr_segment_line',
            'ocrd-tesserocr-segment-word=ocrd_tesserocr.cli:ocrd_tesserocr_segment_word',
            'ocrd-tesserocr-crop=ocrd_tesserocr.cli:ocrd_tesserocr_crop',
            'ocrd-tesserocr-deskew=ocrd_tesserocr.cli:ocrd_tesserocr_deskew',
            'ocrd-tesserocr-binarize=ocrd_tesserocr.cli:ocrd_tesserocr_binarize',
        ]
    },
)
