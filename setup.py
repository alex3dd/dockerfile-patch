#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author: Achraf Cherti (Asher256) <asher256@gmail.com>
# Github: https://github.com/Asher256/python-dockerfile_patch
# License: LGPL 2.1
#
# Setup scripts doc:
# https://docs.python.org/2/distutils/setupscript.html
#
# This source code follows the PEP-8 style guide:
# https://www.python.org/dev/peps/pep-0008/
#
"""setup.py dockerfile_patch."""

from setuptools import setup, find_packages
from codecs import open
from os import path
from dockerfile_patch import __doc__ as DESCRIPTION


SCRIPT_DIR = path.abspath(path.dirname(__file__))

with open(path.join(SCRIPT_DIR, 'README.md'), encoding='utf-8') as fhandler:
    LONG_DESCRIPTION = fhandler.read()


setup(
    name='dockerfile_patch',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.9.0',

    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,

    # The project's main homepage.
    url='https://github.com/Asher256/python-dockerfile_patch',

    # Author details
    author='Asher256',
    author_email='asher256@gmail.com',

    # Choose your license
    license='LGPL2.1',

    platforms=["POSIX"],

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 5 - Production/Stable',

        'Operating System :: POSIX',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU Lesser General '
        'Public License v2 (LGPLv2)'

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],

    # What does your project relate to?
    keywords='dockerfiles dockerfile dockerfiles docker-image docker-images',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=['dockerfile_patch'],

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['dockerfile-parse>=0.0.7', 'PyYAML', 'Jinja2', 'docker'],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={},

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={'dockerfile_patch': ['data/*.sh']},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={},

    # 'scripts' is useful for distributing support tools which are associated
    # with a library, or just taking advantage of the setuptools / PyPI
    # infrastructure to distribute a command line tool that happens to use
    # Python.
    scripts = ['dockerfile-patch']

)

# quicktest: python3 % test
# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
