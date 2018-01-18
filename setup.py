#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

def readme():
    with open('README.md') as readme_file:
        return readme_file.read()

setup(
    name = 'kahelo',
    version = '1.0.1',
    description = 'kahelo - tile management for GPS maps - kahelo.godrago.net',
    long_description=readme(),
    download_url = 'https://github.com/gillesArcas/kahelo',
    url = 'https://github.com/gillesArcas/kahelo',
    author = 'Gilles Arcas',
    author_email = 'gilles.arcas@gmail.com',
    packages = ['kahelo'],
    license = "MIT",
    install_requires = ['six', 'Pillow'],
    classifiers = [
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.4',
        'Topic :: Scientific/Engineering :: GIS',
        ],
    entry_points='''
        [console_scripts]
        kahelo = kahelo.kahelo:kahelo
    ''',
    )
