# -*- coding: utf-8 -*-

import os

from pygcgen import ChangelogGenerator


base_options = [
    "--quiet",
    # "-h",
    # "-v",
    #"-vv",  # or "-v", "-v",
    #"-vvv",
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
    #"--no-issues-wo-labels",
    #
    # "--future-release", "v0.2.0",
    # "--tag-separator", " ---\n\n",
]

ChangelogGenerator(base_options + ["-v"]).run()

on_travis = os.environ.get('TRAVIS', None) == 'True'
if on_travis:
    test = [
        ["--between-tags", "v0.1.1", "v0.2.0"],
        [
            "--since-tag", "v0.1.2",
            "--due-tag", "v0.2.0",
        ],
        [
            "--exclude-labels", "duplicate", "Duplicate",
                                "invalid", "Invalid",
                                "wontfix", "Wontfix",
                                "question", "Question",
                                "hide in changelog",
        ],
        ["--with-unreleased"],
    ]
    for options in test:
        ChangelogGenerator(base_options + options).run()
