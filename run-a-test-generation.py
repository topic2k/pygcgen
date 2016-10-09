# -*- coding: utf-8 -*-

from pygcgen import ChangelogGenerator


options = [
    # "-h",
    "-v",
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
    # "--quiet",
    "--no-overwrite",
    # "--between-tags", "v0.1.1", "v0.2.0",
    # "--between-tags", "v0.1.1",
    # "--since-tag", "v0.1.2",
    # "--due-tag", "v0.2.0",
    # "--include-labels", "bug",
    #"--no-issues-wo-labels",
    #"--with-unreleased",
    # "--future-release", "v0.2.0",
    "--exclude-labels", "duplicate", "Duplicate",
                        "invalid", "Invalid",
                        "wontfix", "Wontfix",
                        "question", "Question",
                        "hide in changelog",
    # "--tag-separator", " ---\n\n",
]

chagen = ChangelogGenerator(options)
chagen.run()
