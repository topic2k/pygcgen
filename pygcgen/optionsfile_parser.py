# -*- coding: utf-8 -*-

import re
try:
    from builtins import object
except ImportError:
    pass


# Pattern to split list options (respecting quotes)
regex = re.compile(
    '\s*(^|,)\s*(["\'])?(?(2)(?P<label1>.*?)\\2|(?P<label2>.*?)((?=,)|$))'
)

FILENAME = ".pygcgen"
KNOWN_INTEGER_KEYS = ["max_issues"]
KNOWN_ARRAY_KEYS = [ # TODO: umbauen auf dict(key: cnt) # cnt=Anzahl:-1=egal
    "between_tags",
    "exclude_labels",
    "exclude_tags"
    "include_labels",
    "section",
]
KNOWN_MULTIPLE_OPTIONS = {
    # False means the option wasn't used in config file
    # Used to overwrite value given by commandline
    "section": False
}
IRREGULAR_OPTIONS = {
    "front_matter": "frontmatter",
    "github_api": "github_endpoint",
    "header_label": "header",
    "issues_label": "issue_prefix",
    "no_author": "author",
    "no_compare_link": "compare_link",
    "no_filter_by_milestone": "filter_issues_by_milestone",
    "no_issues": "issues",
    "no_issues_wo_labels": "add_issues_wo_labels",
    "no_pr_wo_labels": "add_pr_wo_labels",
    "no_pull_requests": "include_pull_request",
    "origin": "git_remote",
    "pr_label": "merge_prefix",
    "author_link_as_tag": "username_as_tag",
}
BOOL_KEYS = {
    "debug": True,
    "no_author": False,
    "no_compare_link": False,
    "no_filter_by_milestone": False,
    "no_issues": False,
    "no_issues_wo_labels": False,
    "no_overwrite": True,
    "no_pr_wo_labels": False,
    "no_pull_requests": False,
    "quiet": False,
    "simple_list": True,
    "unreleased_only": True,
    "unreleased_with_date": True,
    "username_as_tag": False,
    "verbose": True,
    "with_unreleased": True,
}


class ParserError(Exception):
    pass


# ParserFile is a configuration file reader which sets options in the
# given Hash.
#
# In your project's root, you can put a file named
# <tt>.pygcgen</tt> to override defaults.
#
# Example:
#   header_label=# My Super Changelog
#   ; Comments are allowed
#   future-release=5.0.0
#   # Ruby-style comments, too
#   since-tag=1.0.0
#
# The configuration format is
#    <tt>some-key=value</tt>
# or
#    <tt>some_key=value</tt>.
#

class OptionsFileParser(object):
    def __init__(self, options):
        # @param options [Hash] options to be configured from file contents
        # @param file [nil,IO] configuration file handle, defaults to
        # opening `.pygcgen`
        self.options = options
        with open(options.options_file, "r") as fh:
            self.filecontents = fh.read().split("\n")

    def parse(self):
        # Sets options using configuration file content
        line_nr = 0
        for line in self.filecontents:
            line_nr += 1
            self.parse_line(line, line_nr)
        return self.options

    def parse_line(self, line, line_number):
        if not line or self.non_configuration_line(line):
            return
        option_name, value = self.extract_pair(line)

        if option_name in IRREGULAR_OPTIONS:
            option_name = IRREGULAR_OPTIONS[option_name]

        if option_name in KNOWN_MULTIPLE_OPTIONS.keys():
            if self.options.__dict__[option_name] and \
                KNOWN_MULTIPLE_OPTIONS[option_name]:
                self.options.__dict__[option_name].append(
                    self.convert_value(value, option_name)
                )
            else:
                self.options.__dict__[option_name] = [
                    self.convert_value(value, option_name),
                ]
                KNOWN_MULTIPLE_OPTIONS[option_name] = True
        else:
            self.options.__dict__[option_name] = self.convert_value(
                value, option_name
            )

    @staticmethod
    def non_configuration_line(line):
        # Returns true if the line starts with a pound sign or a semi-colon.
        return line.startswith(';') or line.startswith('#')

    @staticmethod
    def extract_pair(line):
        # Returns the option name as a symbol and its string value.
        #
        # @param line [String] unparsed line from config file
        # @return [Array<Symbol, String>]
        try:
            key, value = line.split("=", 2)
        except ValueError:
            key = line
            value = ""
        key = key.strip().lower().replace("-", "_")
        value = value.replace("\\n", "\n")
        return key, value

    @staticmethod
    def convert_value(value, option_name):
        if option_name in KNOWN_ARRAY_KEYS:
            val = []
            for item in regex.finditer(value):
                val.append(
                    item.group("label1") if item.group("label1")
                    else item.group("label2")
                )
            value = val
        elif option_name in KNOWN_INTEGER_KEYS:
            value = int(value)
        elif option_name in BOOL_KEYS:
            if not value:
                value = BOOL_KEYS[option_name]
            elif value.isdigit():
                value = bool(value)
            elif not value.isdigit():
                value = value.strip()[0].lower() in ["t", "y" "1"]
        return value
