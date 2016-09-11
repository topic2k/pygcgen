# -*- coding: utf-8 -*-

from .__main__ import ChangelogGenerator
from .version import __version__

if __name__ == "__main__":
    import sys

    ChangelogGenerator(sys.argv[1:]).run()
