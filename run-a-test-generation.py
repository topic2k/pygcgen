# -*- coding: utf-8 -*-


from pygcgen import ChangelogGenerator
from pygcgen.__main__ import run_gui

run_gui()

exit()

options = ["--options-file", ".pygcgen_example"]

chagen = ChangelogGenerator(options)
chagen.run()
