# -*- coding: utf-8 -*-

###########  original file info from reader.rb  ####################
### #######  https://github.com/skywinder/github-changelog-generator
#
# Author:: Enrico Stahn <mail@enricostahn.com>
#
# Copyright 2014, Zanui, <engineering@zanui.com.au>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
####################################################################

# A Reader to read an existing ChangeLog file and return a structured object
#
# Example:
#   reader = GitHubChangelogGenerator::Reader.new
#   content = reader.read('./CHANGELOG.md')

import re
import sys
if sys.version_info.major == 3:
    from builtins import map


def parse_heading(heading):
    """
    Parse a single heading and return a Hash
    The following heading structures are currently valid:
    - ## [v1.0.2](https://github.com/zanui/chef-thumbor/tree/v1.0.1) (2015-03-24)
    - ## [v1.0.2](https://github.com/zanui/chef-thumbor/tree/v1.0.1)
    - ## v1.0.2 (2015-03-24)
    - ## v1.0.2

    @param [String] heading Heading from the ChangeLog File
    @return [Hash] Returns a structured Hash with version, url and date
    """

    heading_structures = [
        r"^## \[(?P<version>.+?)\]\((?P<url>.+?)\)( \((?P<date>.+?)\))?$",
        r"^## (?P<version>.+?)( \((?P<date>.+?)\))?$",
        ]
    captures = {"version": None, "url": None, "date": None}

    for regexp in heading_structures:
        matches = re.match(regexp, heading)
        if matches:
            captures.update(matches.groupdict())
            break
    return captures


def parse(data):
    """
    Parse the given ChangeLog data into a list of Hashes.

    @param [String] data File data from the ChangeLog.md
    @return [Array<Hash>] Parsed data, e.g. [{ 'version' => ..., 'url' => ..., 'date' => ..., 'content' => ...}, ...]
    """

    sections = re.compile("^## .+$", re.MULTILINE).split(data)
    headings = re.findall("^## .+?$", data, re.MULTILINE)
    sections.pop(0)
    parsed = []

    def func(h, s):
        p = parse_heading(h)
        p["content"] = s
        parsed.append(p)

    list(map(func, headings, sections))
    return parsed


def read_changelog(options):
    with open(options.base, 'r') as fh:
        log = fh.read()
        log = log.lstrip(options.header).strip()
        return parse(log)
