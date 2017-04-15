#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8:tw=75
#
# Copyright © 2017 Peter Jones <Peter Jones@random>
#
# Distributed under terms of the GPLv3 license.

"""
setup.py for https://github.com/vathpela/terminal
"""

from setuptools import setup

setup(
    name='terminal',
    version='1.0',
    license="GPLv3",
    description='Module for interacting with vt100 style terminals',
    author='Peter Jones',
    author_email='pjones@redhat.com',
    url="https://github.com/vathpela/terminal",
    packages=['terminal'],  #same as name
    # install_requires=['bar', 'greek'], #external packages as
    # dependencies
)
