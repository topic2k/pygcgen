# -*- coding: utf-8 -*-

from __future__ import print_function
import os

from pygcgen import ChangelogGenerator


base_options = [
    "--quiet",
    # "-h",
    # "-v",
    # "-vv",  # or "-v", "-v",
    # "-vvv",
    # "--options-file", ".pygcgen_example",
    # "-u", "topic2k",
    # "-p", "pygcgen",
    # '-s', "**Questions:**", "question", "Question",
    # '-s', "**Future-Requests:**", "feature-request",
    # '--section', '**Important changes:**', 'notice',
    # '-s', "**Implemented enhancements:**", "enhancement", "Enhancement",
    # '-s', "**Fixed bugs:**", "bug", "Bug",
    # "-v",
    # "--no-overwrite",
    # "--between-tags", "v0.1.1",
    # "--include-labels", "bug",
    # "--no-issues-wo-labels",
    # "--future-release", "v0.2.0",
    # "--tag-separator", " ---\n\n",
]

on_travis = os.environ.get('TRAVIS', 'false') == 'true'
if not on_travis:
    ChangelogGenerator(base_options + ["-v"]).run()
else:
    tests = [
        [  # Test #01
            "--no-overwrite",
            "--max-simultaneous-requests", "25",
            "--section", '**Important changes:**', 'notice',
            "--since-tag", "v0.1.0",
            "--between-tags", "v0.1.1", "v0.2.1",
            "--due-tag", "v0.2.0",
            "--exclude-tags-regex", "v0\.0\..*",
            "--exclude-tags", "v0.1.2",
            "--with-unreleased",
            "--include-labels", "notice", "enhancement", "bug",
            "--exclude-labels",
            "duplicate", "Duplicate",
            "invalid", "Invalid",
            "wontfix", "Wontfix",
            "question", "Question",
            "hide in changelog",
        ]
    ]
    for nr, options in enumerate(tests, start=1):
        print("starting test {} ...".format(nr), end="")
        ChangelogGenerator(base_options + options).run()
        print(" done.")
