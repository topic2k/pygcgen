# -*- coding: utf-8 -*-

from .__main__ import ChangelogGenerator


if __name__ == "__main__":
    import sys

    ChangelogGenerator(sys.argv[1:]).run()
