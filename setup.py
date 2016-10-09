# -*- coding: utf-8 -*-

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
#from setuptools_scm import get_version


#git_version = get_version()  # root='..', relative_to=__file__)

version = {}
with open("pygcgen/version.py") as fh:
    exec(fh.read(), version)

setup(
    name=version['__title__'],
    version=version['__version__'],
    license=version['__license__'],

    # get the version number from git using setuptools_scm
    # use_scm_version = True,

    keywords=version['__summary__'],
    description='Generate changelog based on tags, issues and '
                'merged pull requests on GitHub.',
    long_description="This package started as a conversion from " \
    "ruby to python of the " \
    "'GitHub Changelog Generator' " \
    "(https://github.com/skywinder/github-changelog-generator).",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Topic :: Software Development :: Documentation",
    ],

    author=version['__author__'],
    author_email=version['__email__'],
    maintainer=version['__author__'],
    maintainer_email=version['__email__'],

    url=version['__uri__'],

    setup_requires=['setuptools_scm', 'setuptools_scm_git_archive', ],
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
        'console_scripts': ['pygcgen = pygcgen.__main__:run', ],
        #'gui_scripts': ['pygcgenw = pygcgen.__main__:run_gui', ],
    },
)
