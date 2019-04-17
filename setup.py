# -*- coding: utf-8 -*-
"""
Installs five executables:

    - ocrd_tesserocr_recognize
    - ocrd_tesserocr_segment_region
    - ocrd_tesserocr_segment_line
    - ocrd_tesserocr_segment_word
    - ocrd_tesserocr_deskew
"""
import codecs

from setuptools import setup, find_packages

setup(
    name='ocrd_tesserocr',
    version='0.2.1',
    description='Tesserocr bindings',
    long_description=codecs.open('README.rst', encoding='utf-8').read(),
    author='Konstantin Baierer, Kay-Michael Würzner',
    author_email='unixprog@gmail.com, wuerzner@gmail.com',
    url='https://github.com/OCR-D/ocrd_tesserocr',
    license='Apache License 2.0',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=open('requirements.txt').read().split('\n'),
    package_data={
        '': ['*.json', '*.yml', '*.yaml'],
    },
    entry_points={
        'console_scripts': [
            'ocrd-tesserocr-recognize=ocrd_tesserocr.cli:ocrd_tesserocr_recognize',
            'ocrd-tesserocr-segment-region=ocrd_tesserocr.cli:ocrd_tesserocr_segment_region',
            'ocrd-tesserocr-segment-line=ocrd_tesserocr.cli:ocrd_tesserocr_segment_line',
            'ocrd-tesserocr-segment-word=ocrd_tesserocr.cli:ocrd_tesserocr_segment_word',
            'ocrd-tesserocr-deskew=ocrd_tesserocr.cli:ocrd_tesserocr_deskew',
        ]
    },
)
