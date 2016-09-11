# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import os
import re
import subprocess
import sys

from .optionsfile_parser import OptionsFileParser
from .version import __version__


DEFAULT_OPTIONS = {
    "bug_labels": ["bug", "Bug"],
    "bug_prefix": "**Fixed bugs:**",
    "date_format": "%Y-%m-%d",
    "enhancement_labels": ["enhancement", "Enhancement"],
    "enhancement_prefix": "**Implemented enhancements:**",
    "exclude_labels": [
        "duplicate","Duplicate",
        "question", "Question",
        "invalid", "Invalid",
        "wontfix", "Wontfix",
    ],
    "git_remote": "origin",
    "github_api": "api.github.com",
    "github_site": "github.com",
    "header": "# Change Log",
    "issue_prefix": "**Closed issues:**",
    "max_issues": sys.maxsize,
    "merge_prefix": "**Merged pull requests:**",
    "output": "CHANGELOG.md",
    "unreleased_label": "Unreleased",
    #"base": "HISTORY.md",
}


class OptionsParser:
    def __init__(self, options=None):
        self.options = self.parse_options(options)

    def parse_options(self, options):
        parser = argparse.ArgumentParser(
            description='Fully automate changelog generation.',
        )

        parser.add_argument(
            "-u", "--user",
            help="Username of the owner of target GitHub repo"
        )
        parser.add_argument(
            "-p", "--project",
            help="Name of project on GitHub"
        )
        parser.add_argument(
            "-t", "--token",
            help="To make more than 50 requests per hour your GitHub token "
                 "is required. You can generate it at: "
                 "https://github.com/settings/tokens/new"
        )
        parser.add_argument(
            "--options-file", metavar="FILE",
            #default=DEFAULT_OPTIONS["options_file"],
            help="Read options from file. Those will overwrite the ones from "
                 "the command line."
        )
        parser.add_argument(
            "-f", "--date-format",
            default=DEFAULT_OPTIONS["date_format"],
            help="The date format to use in changelog. Default is: %%Y-%%m-%%d"
        )
        parser.add_argument(
            "-o", "--output", metavar="FILE",
            default=DEFAULT_OPTIONS["output"],
            help="Output file. Default is CHANGELOG.md"
        )
        parser.add_argument(
            "-b", "--base", metavar="FILE",
            #default=DEFAULT_OPTIONS["base"],
            help="Optional base file to append to generated changelog."
        )
        parser.add_argument(
            "--bugs-label",
            dest="bug_prefix",
            default=DEFAULT_OPTIONS["bug_prefix"],
            help="Setup custom label for bug-fixes section. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["bug_prefix"])
        )
        parser.add_argument(
            "--enhancement-label",
            dest="enhancement_prefix",
            default=DEFAULT_OPTIONS["enhancement_prefix"],
            help="Setup custom label for enhancements section. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["enhancement_prefix"])
        )
        parser.add_argument(
            "--issues-label",
            dest="issue_prefix",
            default=DEFAULT_OPTIONS["issue_prefix"],
            help="Setup custom label for closed-issues section. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["issue_prefix"])
        )
        parser.add_argument(
            "--header-label",
            dest="header",
            default=DEFAULT_OPTIONS["header"],
            help="Setup custom header label. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["header"])
        )
        parser.add_argument(
            "--pr-label",
            dest="merge_prefix",
            default=DEFAULT_OPTIONS["merge_prefix"],
            help="Setup custom label for pull requests section. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["merge_prefix"])
        )
        parser.add_argument(
            "--front-matter", metavar="JSON",
            dest="frontmatter",
            help="Add YAML front matter. Formatted as JSON because it's "
                 "easier to add on the command line."
        )
        parser.add_argument(
            "--no-issues",
            action="store_false", dest='issues',
            help = "Don't include closed issues in changelog."
        )
        parser.add_argument(
            "--no-issues-wo-labels",
            action="store_false", dest="add_issues_wo_labels",
            help="Don't include closed issues without labels in changelog."
        )
        parser.add_argument(
            "--no-pr-wo-labels",
            action="store_false", dest='add_pr_wo_labels',
            help="Don't include pull requests without labels in changelog."
        )
        parser.add_argument(
            "--no-pull-requests",
            action="store_false", dest='include_pull_request',
            help="Don't include pull-requests in changelog."
        )
        parser.add_argument(
            "--no-filter-by-milestone",
            action="store_false", dest="filter_issues_by_milestone",
            help="Don't use milestone to detect when issue was resolved."
        )
        parser.add_argument(
            "--no-author",
            action="store_false", dest="author",
            help="Don't add author of pull-request in the end."
        )
        parser.add_argument(
            "--author-link-as-tag",
            action='store_true', dest="username_as_tag",
            help="Use GitHub tags instead of Markdown links for the "
                 "author of an issue or pull-request."
        )
        parser.add_argument(
            "--with-unreleased",
            action='store_true', dest="with_unreleased",
            help="Include unreleased closed issues in log."
        )
        parser.add_argument(
            "--unreleased-only",
            action='store_true', dest="unreleased_only",
            help="Generate log from unreleased closed issues only."
        )
        parser.add_argument(
            "--unreleased-label",
            default=DEFAULT_OPTIONS["unreleased_label"],
            help="Label for unreleased closed issues. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["unreleased_label"])
        )
        parser.add_argument(
            "--unreleased-with-date",
            action='store_true',
            help="Add actual date to unreleased label."
        )
        parser.add_argument(
            "--no-compare-link",
            action='store_false', dest="compare_link",
            help="Don't include compare link (Full Changelog) between older "
                 "version and newer version."
        )
        parser.add_argument(
            "--include-labels", metavar="LABEL",
            nargs='*',
            help="Only issues with the specified labels will be "
                 "included in the changelog."
        )
        parser.add_argument(
            "--exclude-labels", metavar="LABEL",
            nargs='*', default=DEFAULT_OPTIONS["exclude_labels"],
            help="Issues with the specified labels will always be "
                 "excluded from changelog. "
                 "Default labels: {0}".format(DEFAULT_OPTIONS["exclude_labels"])
        )
        parser.add_argument(
            "--bug-labels", metavar="LABEL",
            nargs='*', default=DEFAULT_OPTIONS["bug_labels"],
            help="Issues with the specified labels will be always added "
                 "to 'Fixed bugs' section. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["bug_labels"])
        )
        parser.add_argument(
            "--enhancement-labels",
            nargs='*', default=DEFAULT_OPTIONS["enhancement_labels"],
            help="Issues with the specified labels will be always added "
                 "to 'Implemented enhancements' section. "
                 "Default is: {0}".format(DEFAULT_OPTIONS["enhancement_labels"])
        )
        parser.add_argument(
            "--between-tags",  metavar="TAG",
            nargs='*', # TODO: nargs=* ?
            help="Changelog will be filled only between specified tags."
        )
        parser.add_argument(
            "--exclude-tags", metavar="TAG",
            nargs='*',
            help="Change log will exclude specified tags."
        )
        parser.add_argument(
            "--exclude-tags-regex",
            nargs=1,
            help='Apply a regular expression on tag names so that they can be '
            'excluded, for example: --exclude-tags-regex ".*\+\d{1,}"'
        )
        parser.add_argument(
            "--since-tag", metavar="TAG",
            help="Change log will start after specified tag."
        )
        parser.add_argument(
            "--due-tag", metavar="TAG",
            help="Change log will end before specified tag."
        )
        parser.add_argument(
            "--max-issues", metavar="NUMBER",
            type=int, default=DEFAULT_OPTIONS["max_issues"],
            help="Max number of issues to fetch from GitHub. "
                 "Default is unlimited."
        )
        parser.add_argument(
            "--release-url", metavar="URL",
            help="The URL to point to for release links, in printf format "
                 "(with the tag as variable)."
        )
        parser.add_argument(
            "--github-api", metavar="URL",
            dest="github_endpoint", default=DEFAULT_OPTIONS["github_api"],
            help="The enterprise endpoint to use for your Github API."
        )
        parser.add_argument(
            "--github-site", metavar="URL",
            dest="github_site", default=DEFAULT_OPTIONS["github_site"],
            help="The Enterprise Github site on which your project is hosted."
        )
        parser.add_argument(
            "--simple-list",
            action='store_true',
            help="Create simple list from issues and pull requests. "
        )
        parser.add_argument(
            "--future-release", metavar="RELEASE_VERSION",
            help="Put the unreleased changes in the specified release number."
        )
        parser.add_argument(
            "--release-branch",
            help="Limit pull requests to the release branch, "
                 "such as master or release."
        )
        parser.add_argument(
            "--origin", dest="git_remote",
            default=DEFAULT_OPTIONS["git_remote"],
            help="If you named the origin of your repo other than origin."
        )
        parser.add_argument(
            "-v", "--verbose",
            action='store_true',
            help="Run verbosely."
        )
        parser.add_argument(
            "--version",
            action='version', version="%(prog)s {0}".format(__version__),
            help="Print version number"
        )
        opts = parser.parse_args(options)
        if not opts.options_file:
            opts.options_file = ".pygcgen"
        if os.path.exists(opts.options_file):
            OptionsFileParser(options=opts).parse()
        if not opts.user or not opts.project:
            self.fetch_user_and_project(opts)
        return opts

    def fetch_user_and_project(self, options):
        user, project = self.user_and_project_from_git(options)
        if not options.user:
            options.user = user
        if not options.project:
            options.project = project

    def user_and_project_from_git(self, options, arg0=None, arg1=None):
        ''' Detects user and project from git. '''
        user, project = self.user_project_from_option(options, arg0, arg1)
        if user and project:
            return user, project

        try:
            remote = subprocess.check_output(['git', 'config', '--get',
             'remote.{0}.url'.format(options.git_remote)
            ])
        except subprocess.CalledProcessError:
            return None, None
        else:
            return self.user_project_from_remote(remote)

    def user_project_from_option(self, options, arg0, arg1):
        '''
        Try to find user and project name from git remote output

        @param [String] output of git remote command
        @return [Array] user and project
        '''

        site = options.github_site
        if arg0 and not arg1:
            # this match should parse strings such as
            #   "https://github.com/skywinder/Github-Changelog-Generator"
            # or
            #   "skywinder/Github-Changelog-Generator"
            #  to user and project
            match = re.match(
                "(?:.+{site}/)?(.+)/(.+)".format(site=site),
                arg0
            )
            if not match:
                print("Can't detect user and name from first "
                      "parameter: '{arg0}' -> exit'".format(arg0=arg0))
                exit(1)
            return match.groups()
        return None, None

    def user_project_from_remote(self, remote):
        '''
        Try to find user and project name from git remote output

        @param [String] output of git remote command
        @return [Array] user and project
        '''

        # try to find repo in format:
        # origin	git@github.com:skywinder/Github-Changelog-Generator.git (fetch)
        # git@github.com:skywinder/Github-Changelog-Generator.git
        regex1 = r".*(?:[:/])(?P<user>(-|\w|\.)*)/(?P<project>(-|\w|\.)*)(\.git).*"
        match = re.match(regex1, remote)
        if match:
            return match.group("user"), match.group("project")

        # try to find repo in format:
        # origin	https://github.com/skywinder/ChangelogMerger (fetch)
        # https://github.com/skywinder/ChangelogMerger
        regex2 = r".*/((?:-|\w|\.)*)/((?:-|\w|\.)*).*"
        match = re.match(regex2, remote)
        if match:
            return match.group("user"), match.group("project")

        return None, None
