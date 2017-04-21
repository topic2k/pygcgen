# -*- coding: utf-8 -*-

from setuptools import setup

version = {}
with open("pygcgen/version.py") as fh:
    exec(fh.read(), version)

setup(
    name=version['__title__'],
    version=version['__version__'],
    license=version['__license__'],

    keywords=version['__summary__'],
    description='Generate changelog based on tags, issues and '
                'merged pull requests on GitHub.',
    long_description="This package started as a conversion from "
    "ruby to python of the 'GitHub Changelog Generator' "
    "(https://github.com/skywinder/github-changelog-generator).",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Documentation",
    ],

    author=version['__author__'],
    author_email=version['__email__'],
    maintainer=version['__author__'],
    maintainer_email=version['__email__'],

    url=version['__uri__'],

    install_requires=["agithub", "python-dateutil"],

    packages=[version['__title__']],
    # data_files=[
    #     ('..', [
    #         'README.md',
    #         'LICENSE',
    #         'CHANGELOG.md',
    #         '.pygcgen_example'
    #     ]),
    # ],
    exclude_package_data={
        '.': ['.gitignore', ]
    },

    entry_points={
        'console_scripts': ['pygcgen = pygcgen.main:run', ],
        #'gui_scripts': ['pygcgenw = pygcgen.main:run_gui', ],
    },
)
