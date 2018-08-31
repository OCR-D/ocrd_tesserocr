# -*- coding: utf-8 -*-
"""
Installs four executables:

    - ocrd_tesserocr_recognize
    - ocrd_tesserocr_segment_region
    - ocrd_tesserocr_segment_line
    - ocrd_tesserocr_segment_word
"""
import codecs

from setuptools import setup, find_packages

with codecs.open('README.rst', encoding='utf-8') as f:
    README = f.read()

setup(
    name='ocrd_tesserocr',
    version='0.1.1',
    description='Tesserocr bindings',
    long_description=README,
    author='Konstantin Baierer',
    author_email='unixprog@gmail.com',
    url='https://github.com/kba/ocrd_tesserocr',
    license='Apache License 2.0',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'ocrd >= 0.7.2',
        'tesserocr >= 2.3.0',
        'click',
    ],
    package_data={
        '': ['*.json', '*.yml', '*.yaml'],
    },
    entry_points={
        'console_scripts': [
            'ocrd-tesserocr-recognize=ocrd_tesserocr.cli:ocrd_tesserocr_recognize',
            'ocrd-tesserocr-segment-region=ocrd_tesserocr.cli:ocrd_tesserocr_segment_region',
            'ocrd-tesserocr-segment-line=ocrd_tesserocr.cli:ocrd_tesserocr_segment_line',
            'ocrd-tesserocr-segment-word=ocrd_tesserocr.cli:ocrd_tesserocr_segment_word',
        ]
    },
)
