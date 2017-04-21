# -*- coding: utf-8 -*-

from __future__ import division, print_function

import copy
import datetime
import re
import sys
import threading
if sys.version_info.major == 3:
    from builtins import object, range, str
from collections import OrderedDict

import dateutil.tz
from dateutil.parser import parse as dateutil_parser

from .fetcher import Fetcher, REPO_CREATED_TAG_NAME
from .pygcgen_exceptions import ChangelogGeneratorError
from .reader import read_changelog


def timestring_to_datetime(timestring):
    """
    Convert an ISO formated date and time string to a datetime object.

    :param str timestring: String with date and time in ISO format.
    :rtype: datetime
    :return: datetime object
    """
    result = dateutil_parser(str(timestring))
    return result


# noinspection PyTypeChecker
class Generator(object):
    """
    A Generator responsible for all logic, related with
    change log generation from ready-to-parse issues.
    """

    def __init__(self, options):
        self.options = options
        self.tag_times_dict = {}
        self.issues = []
        self.issues2 = []
        self.pull_requests = []
        self.all_tags = []
        self.filtered_tags = []
        self.fetcher = Fetcher(options)

    def fetch_and_filter_issues_and_pr(self):
        issues, pull_requests = self.fetcher.fetch_closed_issues_and_pr()

        if self.options.verbose:
            print("Filtering issues and pull requests...")
        self.pull_requests = []
        if self.options.include_pull_request:
            self.pull_requests = self.get_filtered_pull_requests(pull_requests)

        self.issues = []
        if self.options.issues:
            self.issues = self.filter_by_labels(issues, "issues")

        self.fetch_events_for_issues_and_pr()
        self.issues = self.detect_actual_closed_dates(self.issues, "issues")
        self.pull_requests = self.detect_actual_closed_dates(
            self.pull_requests, "pull requests"
        )

    def fetch_events_for_issues_and_pr(self):
        """
        Fetch event for issues and pull requests

        @return [Array] array of fetched issues
        """

        # Async fetching events:
        self.fetcher.fetch_events_async(self.issues, "issues")
        self.fetcher.fetch_events_async(self.pull_requests, "pull requests")

    def fetch_tags_dates(self):
        """ Async fetching of all tags dates. """

        if self.options.verbose:
            print("Fetching dates for {} tags...".format(len(self.filtered_tags)))

        def worker(tag):
            self.get_time_of_tag(tag)

        # Async fetching tags:
        threads = []
        max_threads = 50
        cnt = len(self.filtered_tags)
        for i in range(0, (cnt // max_threads) + 1):
            for j in range(max_threads):
                idx = i * 50 + j
                if idx == cnt:
                    break
                t = threading.Thread(target=worker,
                                     args=(self.filtered_tags[idx],))
                threads.append(t)
                t.start()
                if self.options.verbose > 2:
                    print(".", end="")
            for t in threads:
                t.join()
        if self.options.verbose > 2:
            print(".")
        if self.options.verbose > 1:
            print("Fetched dates for {} tags.".format(
                len(self.tag_times_dict))
            )

    def detect_actual_closed_dates(self, issues, kind):
        """
        Find correct closed dates, if issues was closed by commits.

        :param list issues: issues to check
        :param str kind: either "issues" or "pull requests"
        :rtype: list
        :return: issues with updated closed dates
        """

        if self.options.verbose:
            print("Fetching closed dates for {} {}...".format(
                len(issues), kind)
            )
        all_issues = copy.deepcopy(issues)
        for issue in all_issues:
            if self.options.verbose > 2:
                print(".", end="")
                if not issues.index(issue) % 30:
                    print("")
            self.find_closed_date_by_commit(issue)

            if not issue.get('actual_date', False):
                if issue.get('closed_at', False):
                    print("Skipping closed non-merged issue: #{0} {1}".format(
                        issue["number"], issue["title"]))

                all_issues.remove(issue)

        if self.options.verbose > 2:
            print(".")
        return all_issues

    def find_closed_date_by_commit(self, issue):
        """
        Fill "actual_date" parameter of specified issue by closed date of
        the commit, if it was closed by commit.

        :param dict issue: issue to edit
        """

        if not issue.get('events'):
            return
        # if it's PR -> then find "merged event", in case
        # of usual issue -> find closed date
        compare_string = "merged" if 'merged_at' in issue else "closed"
        # reverse! - to find latest closed event. (event goes in date order)
        # if it were reopened and closed again.
        issue['events'].reverse()
        found_date = False
        for event in issue['events']:
            if event["event"] == compare_string:
                self.set_date_from_event(event, issue)
                found_date = True
                break
        if not found_date:
            # TODO: assert issues, that remain without
            #       'actual_date' hash for some reason.
            print("\nWARNING: Issue without 'actual_date':"
                  " #{0} {1}".format(issue["number"], issue["title"]))

    def set_date_from_event(self, event, issue):
        """
        Set closed date from this issue.

        :param dict event: event data
        :param dict issue: issue data
        """

        if not event.get('commit_id', None):
            issue['actual_date'] = timestring_to_datetime(issue['closed_at'])
            return
        try:
            commit = self.fetcher.fetch_commit(event)
            issue['actual_date'] = timestring_to_datetime(
                commit['author']['date']
            )
        except ValueError:
            print("WARNING: Can't fetch commit {0}. "
                  "It is probably referenced from another repo.".
                  format(event['commit_id']))
            issue['actual_date'] = timestring_to_datetime(issue['closed_at'])

    @staticmethod
    def encapsulate_string(raw_string):
        """
        Encapsulate characters to make markdown look as expected.

        :param str raw_string: string to encapsulate
        :rtype: str
        :return: encapsulated input string
        """

        raw_string.replace('\\', '\\\\')
        enc_string = re.sub("([<>*_()\[\]#])", r"\\\1", raw_string)
        return enc_string

    def compound_changelog(self):
        """
        Main function to start change log generation

        :rtype: str
        :return: Generated change log file
        """

        self.fetch_and_filter_tags()
        tags_sorted = self.sort_tags_by_date(self.filtered_tags)
        self.filtered_tags = tags_sorted
        self.fetch_and_filter_issues_and_pr()

        log = str(self.options.frontmatter) \
            if self.options.frontmatter else u""
        log += u"{0}\n\n".format(self.options.header)

        if self.options.unreleased_only:
            log += self.generate_unreleased_section()
        else:
            log += self.generate_log_for_all_tags()

        try:
            with open(self.options.base) as fh:
                log += fh.read()
        except (TypeError, IOError):
            pass
        return log

    def generate_sub_section(self, issues, prefix):
        """
        Generate formated list of issues for changelog.

        :param list issues: Issues to put in sub-section.
        :param str prefix: Title of sub-section.
        :rtype: str
        :return: Generated ready-to-add sub-section.
        """

        log = ""
        if issues:
            if not self.options.simple_list:
                log += u"{0}\n\n".format(prefix)
            for issue in issues:
                merge_string = self.get_string_for_issue(issue)
                log += u"- {0}\n".format(merge_string)
            log += "\n"
        return log

    def generate_header(self, newer_tag_name, newer_tag_link,
                        newer_tag_time,
                        older_tag_link, project_url):
        """
        Generate a header for a tag section with specific parameters.

        :param str newer_tag_name: Name (title) of newer tag.
        :param str newer_tag_link: Tag name of newer tag, used for links.
                               Could be same as **newer_tag_name** or some
                               specific value, like `HEAD`.
        :param datetime newer_tag_time: Date and time when
                                        newer tag was created.
        :param str older_tag_link: Tag name of older tag, used for links.
        :param str project_url: URL for current project.
        :rtype: str
        :return: Generated ready-to-add tag section.
        """

        log = ""
        # Generate date string:
        # noinspection PyUnresolvedReferences
        time_string = newer_tag_time.strftime(self.options.date_format)

        # Generate tag name and link
        if self.options.release_url:
            release_url = self.options.release_url.format(newer_tag_link)
        else:
            release_url = u"{project_url}/tree/{newer_tag_link}".format(
                project_url=project_url, newer_tag_link=newer_tag_link)

        if not self.options.unreleased_with_date and \
                newer_tag_name == self.options.unreleased_label:
            log += u"# [{newer_tag_name}]({release_url})\n\n".format(
                newer_tag_name=newer_tag_name, release_url=release_url)
        else:
            log += u"# [{newer_tag_name}]({release_url}) " \
                   u"({time_string})\n".format(
                        newer_tag_name=newer_tag_name,
                        release_url=release_url,
                        time_string=time_string
                   )

        if self.options.compare_link \
            and older_tag_link != REPO_CREATED_TAG_NAME:
            # Generate compare link
            log += u"[Full Changelog]"
            log += u"({project_url}/compare/{older_tag_link}".format(
                project_url=project_url,
                older_tag_link=older_tag_link,
            )
            log += u"...{newer_tag_link})\n\n".format(
                newer_tag_link=newer_tag_link
            )
        return log

    def generate_log_between_tags(self, older_tag, newer_tag):
        """
        Generate log between 2 specified tags.

        :param dict older_tag: All issues before this tag's date will be
                               excluded. May be special value, if new tag is
                               the first tag. (Means **older_tag** is when
                               the repo was created.)
        :param dict newer_tag: All issues after this tag's date  will be
                               excluded. May be title of unreleased section.
        :rtype: str
        :return: Generated ready-to-add tag section for newer tag.
        """

        filtered_issues, filtered_pull_requests = \
            self.filter_issues_for_tags(newer_tag, older_tag)

        older_tag_name = older_tag["name"] if older_tag \
            else self.detect_since_tag()

        if not filtered_issues and not filtered_pull_requests:
            # do not generate an unreleased section if it would be empty
            return ""
        return self.generate_log_for_tag(
            filtered_pull_requests, filtered_issues,
            newer_tag, older_tag_name)

    def filter_issues_for_tags(self, newer_tag, older_tag):
        """
        Apply all filters to issues and pull requests.

        :param dict older_tag: All issues before this tag's date will be
                               excluded. May be special value, if new tag is
                               the first tag. (Means **older_tag** is when
                               the repo  was created.)
        :param dict newer_tag: All issues after this tag's date  will be
                               excluded. May be title of unreleased section.
        :rtype: list(dict), list(dict)
        :return: Filtered issues and pull requests.
        """

        filtered_pull_requests = self.delete_by_time(self.pull_requests,
                                                     older_tag, newer_tag)
        filtered_issues = self.delete_by_time(self.issues, older_tag,
                                              newer_tag)

        newer_tag_name = newer_tag["name"] if newer_tag else None

        if self.options.filter_issues_by_milestone:
            # delete excess irrelevant issues (according milestones).Issue #22.
            filtered_issues = self.filter_by_milestone(
                filtered_issues, newer_tag_name, self.issues
            )
            filtered_pull_requests = self.filter_by_milestone(
                filtered_pull_requests, newer_tag_name, self.pull_requests
            )
        return filtered_issues, filtered_pull_requests

    def generate_log_for_all_tags(self):
        """
        The full cycle of generation for whole project.

        :rtype: str
        :return: The complete change log for released tags.
        """

        if self.options.verbose:
            print("Generating log...")
        self.issues2 = copy.deepcopy(self.issues)

        log1 = ""
        if self.options.with_unreleased:
            log1 = self.generate_unreleased_section()

        log = ""
        for index in range(len(self.filtered_tags) - 1):
            log += self.do_generate_log_for_all_tags_part1(log, index)

        if self.options.tag_separator and log1:
            log = log1 + self.options.tag_separator + log
        else:
            log = log1 + log

        if len(self.filtered_tags) != 0:
            log += self.do_generate_log_for_all_tags_part2(log)

        return log

    def do_generate_log_for_all_tags_part1(self, log, index):
        if self.options.verbose > 1:
            print("\tgenerate log for {}".format(
                self.filtered_tags[index]["name"]))
        log2 = self.generate_log_between_tags(
            self.filtered_tags[index + 1], self.filtered_tags[index])
        if self.options.tag_separator and log and log2:
            return self.options.tag_separator + log2
        return log2

    def do_generate_log_for_all_tags_part2(self, log):
        older_tag = self.last_older_tag()
        if self.options.verbose > 1:
            print("\tgenerate log for {}".format(
                self.filtered_tags[-1]["name"]))
        log2 = self.generate_log_between_tags(
            older_tag, self.filtered_tags[-1])
        if self.options.tag_separator and log and log2:
            return self.options.tag_separator + log2
        return log2

    def last_older_tag(self):
        older_tag = {"name": self.get_temp_tag_for_repo_creation()}
        if self.options.between_tags or self.options.since_tag:
            older_tag_date = self.get_time_of_tag(older_tag)
            newer_tag_date = self.get_time_of_tag(self.filtered_tags[-1])
            for tag in self.all_tags:
                tag_date = self.get_time_of_tag(tag)
                if older_tag_date < tag_date < newer_tag_date:
                    older_tag = tag
                    older_tag_date = tag_date
        return older_tag

    def generate_unreleased_section(self):
        """
        Generate log for unreleased closed issues.

        :rtype: str
        :return: Generated ready-to-add unreleased section.
        """
        if not self.filtered_tags:
            return ""
        now = datetime.datetime.utcnow()
        now = now.replace(tzinfo=dateutil.tz.tzutc())
        head_tag = {"name": self.options.unreleased_label}
        self.tag_times_dict[head_tag["name"]] = now
        unreleased_log = self.generate_log_between_tags(
            self.filtered_tags[0], head_tag)
        return unreleased_log

    def get_string_for_issue(self, issue):
        """
        Parse issue and generate single line formatted issue line.

        Example output:
            - Add coveralls integration [\#223](https://github.com/skywinder/github-changelog-generator/pull/223) ([skywinder](https://github.com/skywinder))
            - Add coveralls integration [\#223](https://github.com/skywinder/github-changelog-generator/pull/223) (@skywinder)


        :param dict issue: Fetched issue from GitHub.
        :rtype: str
        :return: Markdown-formatted single issue.
        """

        encapsulated_title = self.encapsulate_string(issue['title'])
        try:
            title_with_number = u"{0} [\\#{1}]({2})".format(
                encapsulated_title, issue["number"], issue["html_url"]
            )
        except UnicodeEncodeError:
            # TODO: why did i add this? Is it needed?
            title_with_number = "ERROR ERROR ERROR: #{0} {1}".format(
                issue["number"], issue['title']
            )
            print(title_with_number, '\n', issue["html_url"])
        return self.issue_line_with_user(title_with_number, issue)

    def issue_line_with_user(self, line, issue):
        """
        If option author is enabled, a link to the profile of the author
        of the pull reqest will be added to the issue line.

        :param str line: String containing a markdown-formatted single issue.
        :param dict issue: Fetched issue from GitHub.
        :rtype: str
        :return: Issue line with added author link.
        """
        if not issue.get("pull_request") or not self.options.author:
            return line

        if not issue.get("user"):
            line += u" (Null user)"
        elif self.options.username_as_tag:
            line += u" (@{0})".format(
                issue["user"]["login"]
            )
        else:
            line += u" ([{0}]({1}))".format(
                issue["user"]["login"], issue["user"]["html_url"]
            )
        return line

    def generate_log_for_tag(self,
                             pull_requests,
                             issues,
                             newer_tag,
                             older_tag_name):
        """
        Generates log for tag section with header and body.

        :param list(dict) pull_requests: List of PR's in this tag section.
        :param list(dict) issues: List of issues in this tag section.
        :param dict newer_tag: Github data of tag for this section.
        :param str older_tag_name: Older tag, used for the links.
                                   May be special value, if **newer tag** is
                                   the first tag. (Means **older_tag** is when
                                   the repo was created.)
        :rtype: str
        :return: Ready-to-add and parsed tag section.
        """

        newer_tag_link, newer_tag_name, \
        newer_tag_time = self.detect_link_tag_time(newer_tag)

        github_site = "https://github.com" or self.options.github_endpoint
        project_url = "{0}/{1}/{2}".format(
            github_site, self.options.user, self.options.project)

        log = self.generate_header(newer_tag_name, newer_tag_link,
                                   newer_tag_time, older_tag_name, project_url)
        if self.options.issues:
            # Generate issues:
            log += self.issues_to_log(issues, pull_requests)
        if self.options.include_pull_request:
            # Generate pull requests:
            log += self.generate_sub_section(
                pull_requests, self.options.merge_prefix
            )
        return log

    def issues_to_log(self, issues, pull_requests):
        """
        Generate ready-to-paste log from list of issues and pull requests.

        :param list(dict) issues: List of issues in this tag section.
        :param list(dict) pull_requests: List of PR's in this tag section.
        :rtype: str
        :return: Generated log for issues and pull requests.
        """

        log = ""
        sections_a, issues_a = self.parse_by_sections(
            issues, pull_requests)

        for section, s_issues in sections_a.items():
            log += self.generate_sub_section(s_issues, section)
        log += self.generate_sub_section(issues_a, self.options.issue_prefix)
        return log

    def parse_by_sections(self, issues, pull_requests):
        """
        This method sort issues by types (bugs, features, etc. or
        just closed issues) by labels.

        :param list(dict) issues: List of issues in this tag section.
        :param list(dict) pull_requests: List of PR's in this tag section.
        :rtype: dict(list(dict)), list(dict)
        :return: Issues and PR's sorted into sections.
        """

        issues_a = []
        sections_a = OrderedDict()

        if not self.options.sections:
            return [sections_a, issues]
        for key in self.options.sections:
            sections_a.update({key: []})
        self.parse_by_sections_for_issues(issues, sections_a, issues_a)
        self.parse_by_sections_for_pr(pull_requests, sections_a)
        return [sections_a, issues_a]

    def parse_by_sections_for_issues(self, issues, sections_a, issues_a):
        for section, sect_labels in self.options.sections.items():
            added_issues = []
            for issue in issues:
                is_labels = issue.get('labels')
                if is_labels:
                    is_lbls = set(l["name"] for l in is_labels)
                    if is_lbls.intersection(set(sect_labels)):
                        sections_a[section].append(issue)
                        added_issues.append(issue)
                        continue
                issues_a.append(issue)
                added_issues.append(issue)
            for iss in added_issues:
                issues.remove(iss)

    def parse_by_sections_for_pr(self, pull_requests, sections_a):
        for section, sect_labels in self.options.sections.items():
            added_pull_requests = []
            for pr in pull_requests:
                pr_labels = pr.get('labels')
                if pr_labels:
                    pr_lbls = set(l["name"] for l in pr_labels)
                    if pr_lbls.intersection(set(sect_labels)):
                        sections_a[section].append(pr)
                        added_pull_requests.append(pr)
                        continue
            for pr in added_pull_requests:
                pull_requests.remove(pr)

    def exclude_issues_by_labels(self, issues):
        """
        Delete all issues with labels from exclude-labels option.

        :param list(dict) issues: All issues for tag.
        :rtype: list(dict)
        :return: Filtered issues.
        """
        if not self.options.exclude_labels:
            return copy.deepcopy(issues)

        remove_issues = set()
        exclude_labels = self.options.exclude_labels
        include_issues = []
        for issue in issues:
            for label in issue["labels"]:
                if label["name"] in exclude_labels:
                    remove_issues.add(issue["number"])
                    break
        for issue in issues:
            if issue["number"] not in remove_issues:
                include_issues.append(issue)
        return include_issues

    def filter_by_milestone(self, filtered_issues, tag_name, all_issues):
        """
        :param list(dict) filtered_issues: Filtered issues.
        :param str tag_name: Name (title) of tag.
        :param list(dict) all_issues: All issues.
        :rtype: list(dict)
        :return: Filtered issues according milestone.
        """

        filtered_issues = self.remove_issues_in_milestones(filtered_issues)
        if tag_name:
            # add missed issues (according milestones)
            issues_to_add = self.find_issues_to_add(all_issues, tag_name)
            filtered_issues.extend(issues_to_add)
        return filtered_issues

    @staticmethod
    def find_issues_to_add(all_issues, tag_name):
        """
        Add all issues, that should be in that tag, according to milestone.

        :param list(dict) all_issues: All issues.
        :param str tag_name: Name (title) of tag.
        :rtype: List[dict]
        :return: Issues filtered by milestone.
        """

        filtered = []
        for issue in all_issues:
            if issue.get("milestone"):
                if issue["milestone"]["title"] == tag_name:
                    iss = copy.deepcopy(issue)
                    filtered.append(iss)
        return filtered

    def remove_issues_in_milestones(self, filtered_issues):
        """
        :param list(dict) filtered_issues: Filtered issues.
        :rtype: list(dict)
        :return: List with removed issues, that contain milestones with
                 same name as a tag.
        """
        for issue in filtered_issues:
            # leave issues without milestones
            if issue["milestone"]:
                # check, that this milestone is in tag list:
                for tag in self.filtered_tags:
                    if tag["name"] == issue["milestone"]["title"]:
                        filtered_issues.remove(issue)
        return filtered_issues

    def delete_by_time(self, issues, older_tag, newer_tag):
        """
        Filter issues that belong to specified tag range.

        :param list(dict) issues: Issues to filter.
        :param dict older_tag: All issues before this tag's date will be
                               excluded. May be special value, if **newer_tag**
                               is the first tag. (Means **older_tag** is when
                               the repo was created.)
        :param dict newer_tag: All issues after this tag's date  will be
                               excluded. May be title of unreleased section.
        :rtype: list(dict)
        :return: Filtered issues.
        """

        if not older_tag and not newer_tag:
            # in case if no tags are specified - return unchanged array
            return copy.deepcopy(issues)

        newer_tag_time = self.get_time_of_tag(newer_tag)
        older_tag_time = self.get_time_of_tag(older_tag)
        filtered = []
        for issue in issues:
            if issue.get('actual_date'):
                rslt = older_tag_time < issue['actual_date'] <= newer_tag_time
                if rslt:
                    filtered.append(copy.deepcopy(issue))
        return filtered

    def include_issues_by_labels(self, all_issues):
        """
        Include issues with labels, specified in self.options.include_labels.

        :param list(dict) all_issues: All issues.
        :rtype: list(dict)
        :return: Filtered issues.
        """

        included_by_labels = self.filter_by_include_labels(all_issues)
        wo_labels = self.filter_wo_labels(all_issues)
        il = set([f["number"] for f in included_by_labels])
        wl = set([w["number"] for w in wo_labels])
        filtered_issues = []
        for issue in all_issues:
            if issue["number"] in il or issue["number"] in wl:
                filtered_issues.append(issue)
        return filtered_issues

    def filter_wo_labels(self, all_issues):
        """
        Filter all issues that don't have a label.

        :rtype: list(dict)
        :return: Issues without labels.
        """

        issues_wo_labels = []
        if not self.options.add_issues_wo_labels:
            for issue in all_issues:
                if not issue['labels']:
                    issues_wo_labels.append(issue)
        return issues_wo_labels

    def filter_by_include_labels(self, issues):
        """
        Filter issues to include only issues with labels
        specified in include_labels.

        :param list(dict) issues: Pre-filtered issues.
        :rtype: list(dict)
        :return: Filtered issues.
        """

        if not self.options.include_labels:
            return copy.deepcopy(issues)
        filtered_issues = []
        include_labels = set(self.options.include_labels)
        for issue in issues:
            labels = [label["name"] for label in issue["labels"]]
            if include_labels.intersection(labels):
                filtered_issues.append(issue)
        return filtered_issues

    def filter_by_labels(self, all_issues, kind):
        """
        Filter issues for include/exclude labels.

        :param list(dict) all_issues: All issues.
        :param str kind: Either "issues" or "pull requests".
        :rtype: list(dict)
        :return: Filtered issues.
        """

        filtered_issues = self.include_issues_by_labels(all_issues)
        filtered = self.exclude_issues_by_labels(filtered_issues)
        if self.options.verbose > 1:
            print("\tremaining {}: {}".format(kind, len(filtered)))
        return filtered

    def get_filtered_pull_requests(self, pull_requests):
        """
        This method fetches missing params for PR and filter them
        by specified options. It include add all PR's with labels
        from options.include_labels and exclude all from
        options.exclude_labels.

        :param list(dict) pull_requests: All pull requests.
        :rtype: list(dict)
        :return: Filtered pull requests.
        """

        pull_requests = self.filter_by_labels(pull_requests, "pull requests")
        pull_requests = self.filter_merged_pull_requests(pull_requests)
        if self.options.verbose > 1:
            print("\tremaining pull requests: {}".format(len(pull_requests)))
        return pull_requests

    def filter_merged_pull_requests(self, pull_requests):
        """
        This method filter only merged PR and fetch missing required
        attributes for pull requests. Using merged date is more correct
        than closed date.

        :param list(dict) pull_requests: Pre-filtered pull requests.
        :rtype: list(dict)
        :return:
        """

        if self.options.verbose:
            print("Fetching merge date for pull requests...")
        closed_pull_requests = self.fetcher.fetch_closed_pull_requests()

        if not pull_requests:
            return []
        pulls = copy.deepcopy(pull_requests)
        for pr in pulls:
            fetched_pr = None
            for fpr in closed_pull_requests:
                if fpr['number'] == pr['number']:
                    fetched_pr = fpr
            if fetched_pr:
                pr['merged_at'] = fetched_pr['merged_at']
                closed_pull_requests.remove(fetched_pr)

        for pr in pulls:
            if not pr.get('merged_at'):
                pulls.remove(pr)
        return pulls

    def fetch_and_filter_tags(self):
        """
        Fetch and filter tags, fetch dates and sort them in time order.
        """

        self.all_tags = self.fetcher.get_all_tags()
        self.filtered_tags = self.get_filtered_tags(self.all_tags)
        self.fetch_tags_dates()

    def sort_tags_by_date(self, tags):
        """
        Sort all tags by date.

        :param list(dict) tags: All tags.
        :rtype: list(dict)
        :return: Sorted list of tags.
        """

        if self.options.verbose:
            print("Sorting tags...")
        tags.sort(key=lambda x: self.get_time_of_tag(x))
        tags.reverse()
        return tags

    def get_time_of_tag(self, tag):
        """
        Get date and time for tag, fetching it if not already cached.

        :param dict tag: Tag to get the datetime for.
        :rtype: datetime
        :return: datetime for specified tag.
        """

        if not tag:
            raise ChangelogGeneratorError("tag is nil")

        name_of_tag = tag["name"]
        time_for_name = self.tag_times_dict.get(name_of_tag, None)
        if time_for_name:
            return time_for_name
        else:
            time_string = self.fetcher.fetch_date_of_tag(tag)
            try:
                self.tag_times_dict[name_of_tag] = \
                    timestring_to_datetime(time_string)
            except UnicodeWarning:
                print("ERROR ERROR:", tag)
                self.tag_times_dict[name_of_tag] = \
                    timestring_to_datetime(time_string)
            return self.tag_times_dict[name_of_tag]

    def detect_link_tag_time(self, tag):
        """
        Detect link, name and time for specified tag.

        :param dict tag: Tag data.
        :rtype: str, str, datetime
        :return: Link, name and time of the tag.
        """

        # if tag is nil - set current time
        newer_tag_time = self.get_time_of_tag(tag) if tag \
            else datetime.datetime.now()

        # if it's future release tag - set this value
        if tag["name"] == self.options.unreleased_label \
            and self.options.future_release:
            newer_tag_name = self.options.future_release
            newer_tag_link = self.options.future_release
        elif tag["name"] is not self.options.unreleased_label :
            # put unreleased label if there is no name for the tag
            newer_tag_name = tag["name"]
            newer_tag_link = newer_tag_name
        else:
            newer_tag_name = self.options.unreleased_label
            newer_tag_link = "HEAD"
        return [newer_tag_link, newer_tag_name, newer_tag_time]

    def detect_since_tag(self):
        """
        Try to find tag name to use as older tag for range of log creation.

        :rtype: str
        :return: Tag name to use as 'oldest' tag. May be special value,
                 indicating the creation of the repo.
        """
        return self.options.since_tag or self.version_of_first_item()

    def version_of_first_item(self):
        """
        Try to detect the newest tag from self.options.base, otherwise
        return a special value indicating the creation of the repo.

        :rtype: str
        :return: Tag name to use as 'oldest' tag. May be special value,
                 indicating the creation of the repo.
        """
        try:
            sections = read_changelog(self.options)
            return sections[0]["version"]
        except(IOError, TypeError):
            return self.get_temp_tag_for_repo_creation()

    def get_temp_tag_for_repo_creation(self):
        """
        If not already cached, fetch the creation date of the repo, cache it
        and return the special value indicating the creation of the repo.

        :rtype: str
        :return: value indicating the creation
        """
        tag_date = self.tag_times_dict.get(REPO_CREATED_TAG_NAME, None)
        if not tag_date:
            tag_name, tag_date = self.fetcher.fetch_repo_creation_date()
            self.tag_times_dict[tag_name] = timestring_to_datetime(tag_date)
        return REPO_CREATED_TAG_NAME

    def get_filtered_tags(self, all_tags):
        """
        Return tags after filtering tags in lists provided by
        option: --between-tags & --exclude-tags

        :param list(dict) all_tags: All tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """

        filtered_tags = self.filter_since_tag(all_tags)
        if self.options.between_tags:
            filtered_tags = self.filter_between_tags(filtered_tags)
        if self.options.due_tag:
            filtered_tags = self.filter_due_tag(filtered_tags)
        return self.filter_excluded_tags(filtered_tags)

    def filter_since_tag(self, all_tags):
        """
        Filter tags according since_tag option.

        :param list(dict) all_tags: All tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """

        tag = self.detect_since_tag()
        if not tag or tag == REPO_CREATED_TAG_NAME:
            return copy.deepcopy(all_tags)

        filtered_tags = []
        tag_names = [t["name"] for t in all_tags]
        try:
            idx = tag_names.index(tag)
        except ValueError:
            self.warn_if_tag_not_found(tag, "since-tag")
            return copy.deepcopy(all_tags)

        since_tag = all_tags[idx]
        since_date = self.get_time_of_tag(since_tag)
        for t in all_tags:
            tag_date = self.get_time_of_tag(t)
            if since_date <= tag_date:
                filtered_tags.append(t)
        return filtered_tags

    def filter_due_tag(self, all_tags):
        """
        Filter tags according due_tag option.

        :param list(dict) all_tags: Pre-filtered tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """

        filtered_tags = []
        tag = self.options.due_tag
        tag_names = [t["name"] for t in all_tags]
        try:
            idx = tag_names.index(tag)
        except ValueError:
            self.warn_if_tag_not_found(tag, "due-tag")
            return copy.deepcopy(all_tags)

        due_tag = all_tags[idx]
        due_date = self.get_time_of_tag(due_tag)
        for t in all_tags:
            tag_date = self.get_time_of_tag(t)
            if tag_date <= due_date:
                filtered_tags.append(t)
        return filtered_tags

    def filter_between_tags(self, all_tags):
        """
        Filter tags according between_tags option.

        :param list(dict) all_tags: Pre-filtered tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """

        tag_names = [t["name"] for t in all_tags]
        between_tags = []
        for tag in self.options.between_tags:
            try:
                idx = tag_names.index(tag)
            except ValueError:
                raise ChangelogGeneratorError(
                    "ERROR: can't find tag {0}, specified with "
                    "--between-tags option.".format(tag))
            between_tags.append(all_tags[idx])

        between_tags = self.sort_tags_by_date(between_tags)

        if len(between_tags) == 1:
            # if option --between-tags was only 1 tag given, duplicate it
            # to generate the changelog only for that one tag.
            between_tags.append(between_tags[0])

        older = self.get_time_of_tag(between_tags[1])
        newer = self.get_time_of_tag(between_tags[0])

        for tag in all_tags:
            if older < self.get_time_of_tag(tag) < newer:
                between_tags.append(tag)
        if older == newer:
            between_tags.pop(0)
        return between_tags

    def filter_excluded_tags(self, all_tags):
        """
        Filter tags according exclude_tags and exclude_tags_regex option.

        :param list(dict) all_tags: Pre-filtered tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """
        filtered_tags = copy.deepcopy(all_tags)
        if self.options.exclude_tags:
            filtered_tags = self.apply_exclude_tags(filtered_tags)
        if self.options.exclude_tags_regex:
            filtered_tags = self.apply_exclude_tags_regex(filtered_tags)
        return filtered_tags

    def apply_exclude_tags_regex(self, all_tags):
        """
        Filter tags according exclude_tags_regex option.

        :param list(dict) all_tags: Pre-filtered tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """
        filtered = []
        for tag in all_tags:
            if not re.match(self.options.exclude_tags_regex, tag["name"]):
                filtered.append(tag)
        if len(all_tags) == len(filtered):
            self.warn_if_nonmatching_regex()
        return filtered

    def apply_exclude_tags(self, all_tags):
        """
        Filter tags according exclude_tags option.

        :param list(dict) all_tags: Pre-filtered tags.
        :rtype: list(dict)
        :return: Filtered tags.
        """
        filtered = copy.deepcopy(all_tags)
        for tag in all_tags:
            if tag["name"] not in self.options.exclude_tags:
                self.warn_if_tag_not_found(tag, "exclude-tags")
            else:
                filtered.remove(tag)
        return filtered

    def warn_if_nonmatching_regex(self):
        if not self.options.quiet:
            print(
                "WARNING: unable to reject any tag, using regex "
                "'{0}' in --exclude-tags-regex option.".format(
                    self.options.exclude_tags_regex
                )
            )

    def warn_if_tag_not_found(self, tag, option):
        if not self.options.quiet:
            print(
                "WARNING: can't find tag '{0}' specified with "
                "--{1} option.".format(tag, option)
            )
