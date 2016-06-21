# -*- coding: utf-8 -*-

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
from pygcgen.version import version


setup(
    name = 'pygcgen',
    version = version,
    use_scm_version = True,
    description = 'Fully automate changelog generation.',
    long_description = 'Automatically generate change log from your tags, '
                     'issues, labels and pull requests on GitHub',
    author = 'skywinder (Ruby-version), topic2k (Python-version',
    author_email = 'sky4winder+github@gmail.com, topic2k@atlogger.de',
    maintainer = 'topic2k',
    maintainer_email = 'topic2k@atlogger.de',
    url = 'https://topic2k.github.io/pygcgen/',
    download_url = 'https://github.com/topic2k/pygcgen/zipball/master',
    license = 'The MIT License (MIT)',
    packages =  ['pygcgen'],
    setup_requires = ['setuptools', 'setuptools_scm',],
    install_requires = ["agithub", "python-dateutil"],
    dependency_links = [r"https://github.com/jpaugh/agithub/archive/master.zip",],
    entry_points = {
        'console_scripts': ['pygcgen = pygcgen.__main__:run',],
        'gui_scripts': ['pywgcgen = pygcgen.__main__:run_gui',],
    },
    keywords = "github changelog",
    exclude_package_data = {
        '' : ['.gitignore', 'TODO.txt']
    },
)
