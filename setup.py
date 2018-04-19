# -*- coding: utf-8 -*-
"""
Installs three binaries:

    - ocrd_tesserocr_segment_line
    - ocrd_tesserocr_segment_region
    - ocrd_tesserocr_recognize
"""
import codecs

from setuptools import setup, find_packages

with codecs.open('README.rst', encoding='utf-8') as f:
    README = f.read()

with codecs.open('LICENSE', encoding='utf-8') as f:
    LICENSE = f.read().encode('utf-8')

setup(
    name='ocrd_tesserocr',
    version='0.0.1',
    description='Tesserocr bindings',
    long_description=README,
    author='Konstantin Baierer',
    author_email='unixprog@gmail.com',
    url='https://github.com/kba/ocrd_tesserocr',
    license='Apache License 2.0',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'ocrd >= 0.0.6',
        'click',
        'tesserocr',
    ],
    entry_points={
        'console_scripts': [
            'ocrd-tesserocr-segment-region=ocrd_tesserocr.cli:ocrd_tesserocr_segment_region',
            'ocrd-tesserocr-segment-line=ocrd_tesserocr.cli:ocrd_tesserocr_segment_line',
            'ocrd-tesserocr-recognize=ocrd_tesserocr.cli:ocrd_tesserocr_recognize',
        ]
    },
)
