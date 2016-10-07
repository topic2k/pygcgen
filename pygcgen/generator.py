# -*- coding: utf-8 -*-


from __future__ import print_function
from __future__ import division
from builtins import str
from builtins import range
from builtins import object
from dateutil.parser import parse as dateutil_parser
import dateutil.tz

import re
import copy
import threading
import datetime

from .fetcher import Fetcher
from .reader import read_changelog
from .pygcgen_exceptions import ChangelogGeneratorError


REPO_CREATED_KEY = "repo_created_at"

def dt_parser(timestring):
    result = dateutil_parser(str(timestring))
    return result


class Generator(object):
    ''' A Generator responsible for all logic, related with
    change log generation from ready-to-parse issues. '''

    def __init__(self, options):
        self.options = options
        self.tag_times_dict = {}
        self.fetcher = Fetcher(options)

    def fetch_issues_and_pr(self):
        issues, pull_requests = self.fetcher.fetch_closed_issues_and_pr()

        self.pull_requests = []
        if self.options.include_pull_request:
            self.pull_requests = self.get_filtered_pull_requests(pull_requests)

        self.issues = []
        if self.options.issues:
            self.issues = self.get_filtered_issues(issues)

        self.fetch_events_for_issues_and_pr()
        self.issues = self.detect_actual_closed_dates(self.issues, "issues")
        self.pull_requests = self.detect_actual_closed_dates(self.pull_requests, "pull requests")

    def fetch_events_for_issues_and_pr(self):
        '''
        Fetch event for issues and pull requests

        @return [Array] array of fetched issues
        '''

        if self.options.verbose:
            print("Fetching events for issues and PR: {0}".format(
                len(self.issues) + len(self.pull_requests)
            ))

        # Async fetching events:
        self.fetcher.fetch_events_async(self.issues, "issues")
        self.fetcher.fetch_events_async(self.pull_requests, "pull requests")

    def fetch_tags_dates(self):
        ''' Async fetching of all tags dates. '''

        if self.options.verbose:
            print("Fetching tag dates (async)...")

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
                if self.options.verbose:
                    print(".", end="")
            for t in threads:
                t.join()

        if self.options.verbose:
            print("\nFetched tags dates count: {0}".format(
                len(self.tag_times_dict)))

    def detect_actual_closed_dates(self, issues, kind):
        ''' Find correct closed dates, if issues was closed by commits. '''

        if self.options.verbose:
            print("Fetching closed dates for {0}...".format(kind))
        all_issues = copy.deepcopy(issues)
        for issue in all_issues:
            if self.options.verbose:
                print(".", end="")
                if not issues.index(issue) % 30:
                    print("")
            self.find_closed_date_by_commit(issue)
            if not issue.get('actual_date', False):
                # TODO: don't remove it ???
                print("\nHELP ME! is it correct to skip #{0} {1}?".format(issue["number"], issue["title"]))
                issues.remove(issue)

        if self.options.verbose:
            print("\nDone.")
        return all_issues

    def find_closed_date_by_commit(self, issue):
        '''
        Fill "actual_date" parameter of specified issue by closed date of
        the commit, if it was closed by commit.

        @param [Hash] issue
        '''

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
                break       #else:
        if not found_date:
            # TODO: assert issues, that remain without
            #       'actual_date' hash for some reason.
            print("\nWARNING: Issue without 'actual_date':"
                   " #{0} {1}".format(issue["number"], issue["title"]))

    def set_date_from_event(self, event, issue):
        '''
        Set closed date from this issue.

        @param [Hash] event
        @param [Hash] issue
        '''

        if not event.get('commit_id', None):
            issue['actual_date'] = dt_parser(issue['closed_at'])
            return
        try:
            commit = self.fetcher.fetch_commit(event)
            issue['actual_date'] = dt_parser(commit['author']['date'])
        #except UnicodeWarning:
        #    print(commit)
        #    issue['actual_date'] = dt_parser(commit['author']['date'])
        except ValueError:
            print("WARNING: Can't fetch commit {0}. "
                  "It is probably referenced from another repo.".
                  format(event['commit_id']))
            issue['actual_date'] = dt_parser(issue['closed_at'])

    def encapsulate_string(self, string):
        '''
        Encapsulate characters to make markdown look as expected.

        @param [String] string
        @return [String] encapsulated input string
        '''

        string.replace('\\', '\\\\')
        string = re.sub("([<>*_()\[\]#])", r"\\\1", string)
        return string

    def compound_changelog(self):
        '''
        Main function to start change log generation

        @return [String] Generated change log file
        '''

        self.fetch_and_filter_tags()
        tags_sorted = self.sort_tags_by_date(self.filtered_tags)
        self.filtered_tags = tags_sorted
        self.fetch_issues_and_pr()

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
        '''
        @param [Array] issues List of issues on sub-section
        @param [String] prefix Name of sub-section
        @return [String] Generate ready-to-go sub-section
        '''

        log = ""
        if issues:
            if not self.options.simple_list:
                log += u"{0}\n\n".format(prefix)
            for issue in issues:
                merge_string = self.get_string_for_issue(issue)
                log += u"- {0}\n".format(merge_string)
            log += "\n"
        return log

    def generate_header(self, newer_tag_name, newer_tag_link, newer_tag_time,
                        older_tag_link, project_url):
        '''
        It generate one header for section with specific parameters.

        @param [String] newer_tag_name - name of newer tag
        @param [String] newer_tag_link - used for links. Could be same
                                         as 'newer_tag_name' or some
                                         specific value, like HEAD
        # @param [Time] newer_tag_time - time, when newer tag created
        # @param [String] older_tag_link - tag name, used for links.
        # @param [String] project_url - url for current project.
        # @return [String] - Generate one ready-to-add section.
        '''

        log = ""
        # Generate date string:
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
                        time_string=time_string)

        if self.options.compare_link and older_tag_link != REPO_CREATED_KEY:
            # Generate compare link
            log += u"[Full Changelog]({project_url}/compare/{older_tag_link}" \
                   u"...{newer_tag_link})\n\n".format(
                project_url=project_url, older_tag_link=older_tag_link,
                newer_tag_link=newer_tag_link)
        return log

    def generate_log_between_tags(self, older_tag, newer_tag):
        '''
        Generate log only between 2 specified tags

        @param [String] older_tag all issues before this tag date will be
                                  excluded. May be nil, if it's first tag.
        @param [String] newer_tag all issue after this tag will be excluded.
                                  May be nil for unreleased section.
        '''

        filtered_issues, filtered_pull_requests = \
            self.filter_issues_for_tags(newer_tag, older_tag)

        older_tag_name = older_tag["name"] if older_tag else self.detect_since_tag()

        if not filtered_issues and not filtered_pull_requests:
            # do not generate an unreleased section if it would be empty
            return ""
        return self.generate_log_for_tag(
            filtered_pull_requests, filtered_issues,
            newer_tag, older_tag_name)

    def filter_issues_for_tags(self, newer_tag, older_tag):
        '''
        Apply all filters to issues and pull requests.

        @return [Array] filtered issues and pull requests
        '''

        filtered_pull_requests = self.delete_by_time(self.pull_requests,
                                                     older_tag, newer_tag)
        filtered_issues = self.delete_by_time(self.issues, older_tag,
                                              newer_tag)

        newer_tag_name = newer_tag["name"] if newer_tag else None

        if self.options.filter_issues_by_milestone:
            # delete excess irrelevant issues (according milestones).Issue #22.
            filtered_issues = self.filter_by_milestone(
                filtered_issues, newer_tag_name, self.issues)
            filtered_pull_requests = self.filter_by_milestone(
                filtered_pull_requests, newer_tag_name, self.pull_requests)
        return filtered_issues, filtered_pull_requests

    def generate_log_for_all_tags(self):
        '''
        The full cycle of generation for whole project

        @return [String] The complete change log
        '''

        if self.options.verbose:
            print("Generating log...")
        self.issues2 = copy.deepcopy(self.issues)

        log1 = ""
        if self.options.with_unreleased:
            log1 = self.generate_unreleased_section()

        log = ""
        for index in range(len(self.filtered_tags)-1):
            if self.options.verbose:
                print("\tgenerate log for {0}".format(
                    self.filtered_tags[index]["name"]))
            log2 = self.generate_log_between_tags(
                self.filtered_tags[index + 1], self.filtered_tags[index])
            if self.options.tag_separator and log and log2:
                log = log + self.options.tag_separator + log2
            else:
                log += log2

        if self.options.tag_separator and log1:
            log = log1 + self.options.tag_separator + log
        else:
            log = log1 + log

        if len(self.filtered_tags) != 0:
            older_tag = {"name": self.get_temp_tag_for_repo_creation()}
            if self.options.between_tags or self.options.since_tag:
                older = self.get_time_of_tag(older_tag)
                newer = self.get_time_of_tag(self.filtered_tags[-1])
                for tag in self.all_tags:
                    tag_date = self.get_time_of_tag(tag)
                    if older < tag_date < newer:
                        older_tag = tag
                        older = tag_date
            if self.options.verbose:
                print("\tgenerate log for {0}".format(
                    self.filtered_tags[-1]["name"]))
            log2 = self.generate_log_between_tags(
                older_tag, self.filtered_tags[-1])
            if self.options.tag_separator and log and log2:
                log = log + self.options.tag_separator + log2
            else:
                log += log2
        return log

    def generate_unreleased_section(self):
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
        '''
        Parse issue and generate single line formatted issue line.
        Example output:
        - Add coveralls integration [\#223](https://github.com/skywinder/github-changelog-generator/pull/223) ([skywinder](https://github.com/skywinder))
        - Add coveralls integration [\#223](https://github.com/skywinder/github-changelog-generator/pull/223) (@skywinder)

        @param [Hash] issue Fetched issue from GitHub
        @return [String] Markdown-formatted single issue
        '''

        encapsulated_title = self.encapsulate_string(issue['title'])
        try:
            title_with_number = u"{0} [\\#{1}]({2})".format(
            encapsulated_title, issue["number"], issue["html_url"])
        except UnicodeEncodeError:
            # TODO: why did i add this? Is it needed?
            print(encapsulated_title)
            print(issue["number"])
            print(issue["html_url"])
            title_with_number = "ERROR ERROR ERROR"
        return self.issue_line_with_user(title_with_number, issue)

    def issue_line_with_user(self, line, issue):
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

    def generate_log_for_tag(self, pull_requests, issues,
                             newer_tag, older_tag_name=None):
        '''
        Generates log for section with header and body.

        @param [Array] pull_requests List or PR's in new section
        @param [Array] issues List of issues in new section
        @param [String] newer_tag Name of the newer tag.
                                  Could be nil for `Unreleased` section
        @param [String] older_tag_name Older tag, used for the links.
                                       Could be nil for last tag.
        @return [String] Ready and parsed section
        '''

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
            log += self.generate_sub_section(pull_requests, self.options.merge_prefix)
        return log

    def issues_to_log(self, issues, pull_requests):
        '''
        Generate ready-to-paste log from list of issues and pull requests.

        @param [Array] issues
        @param [Array] pull_requests
        @return [String] generated log for issues
        '''

        log = ""
        sections_a, issues_a = self.parse_by_sections(
            issues, pull_requests)

        for section, s_issues in sections_a.items():
            log += self.generate_sub_section(s_issues, section)
        log += self.generate_sub_section(issues_a, self.options.issue_prefix)
        return log

    def parse_by_sections(self, issues, pull_requests):
        '''
        This method sort issues by types (bugs, features, or
        just closed issues) by labels.

        @param [Array] issues
        @param [Array] pull_requests
        @return [Array] tuple of filtered arrays: (Bugs, Enhancements Issues)
        '''

        issues_a = []
        sections_a = {key:[] for key in self.options.sections.keys()}

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

        return [sections_a, issues_a]

    def exclude_issues_by_labels(self, issues):
        '''
        Delete all labels with labels from self.options.exclude_labels array.

        # @param [Array] issues
        # @return [Array] filtered array
        '''
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
        '''
        @return [Array] filtered issues according milestone
        '''

        filtered_issues = self.remove_issues_in_milestones(filtered_issues)
        if tag_name:
            # add missed issues (according milestones)
            issues_to_add = self.find_issues_to_add(all_issues, tag_name)
            filtered_issues.extend(issues_to_add)
        return filtered_issues

    def find_issues_to_add(self, all_issues, tag_name):
        '''
        Add all issues, that should be in that tag, according milestone

        @param [Array] all_issues
        @param [String] tag_name
        @return [Array] issues with milestone #tag_name
        '''

        filtered = []
        for issue in all_issues:
            if issue.get("milestone"):
                if issue["milestone"]["title"] == tag_name:
                    iss = copy.deepcopy(issue)
                    filtered.append(iss)
        return filtered

    def remove_issues_in_milestones(self, filtered_issues):
        '''
        @return [Array] array with removed issues, that contain
                        milestones with same name as a tag
        '''
        for issue in filtered_issues:
            # leave issues without milestones
            if issue["milestone"]:
                # check, that this milestone is in tag list:
                for tag in self.filtered_tags:
                    if tag["name"] == issue["milestone"]["title"]:
                        filtered_issues.remove(issue)
        return filtered_issues

    def delete_by_time(self, issues, older_tag=None, newer_tag=None):
        '''
        Method filter issues, that belong only specified tag range.

        @param [Array]  issues issues to filter
        @param [Symbol] hash_key key of date value default is :actual_date
        @param [String] older_tag all issues before this tag date will
                                  be excluded. May be nil, if it's first tag
        @param [String] newer_tag all issue after this tag will be excluded.
                                  May be nil for unreleased section
        @return [Array] filtered issues
        '''

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

    def tag_older_new_tag(self, newer_tag_time, time):
        if not newer_tag_time:
            return True
        tag_time = dt_parser(newer_tag_time)
        return time <= tag_time

    def tag_newer_old_tag(self, older_tag_time, time):
        if not older_tag_time:
            return True
        tag_time = dt_parser(older_tag_time)
        return time > tag_time

    def include_issues_by_labels(self, all_issues):
        '''
        Include issues with labels, specified in self.options.include_labels.

        @param [Array] issues to filter
        @return [Array] filtered array of issues
        '''

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
        '''
        @return [Array] issues without labels or empty array
                        if add_issues_wo_labels is false
        '''

        issues_wo_labels = []
        if self.options.add_issues_wo_labels:
            for issue in all_issues:
                if not issue['labels']:
                    issues_wo_labels.append(issue)
        return issues_wo_labels

    def filter_by_include_labels(self, issues):
        ''' Include issues with labels, specified in include_labels. '''

        if not self.options.include_labels:
            return copy.deepcopy(issues)
        filtered_issues = []
        include_labels = set(self.options.include_labels)
        for issue in issues:
            labels = [label.name for label in issue.labels]
            if include_labels.intersection(labels):
                filtered_issues.append(issue)
        return filtered_issues

    def filter_array_by_labels(self, all_issues):
        '''
        General filter function.

        @param [Array] all_issues
        @return [Array] filtered issues
        '''

        filtered_issues = self.include_issues_by_labels(all_issues)
        filtered = self.exclude_issues_by_labels(filtered_issues)
        return filtered

    def get_filtered_issues(self, issues):
        '''
        Filter issues according labels.

        # @return [Array] Filtered issues
        '''

        issues = self.filter_array_by_labels(issues)
        if self.options.verbose:
            print("Filtered issues: {0}".format(len(issues)))
        return issues

    def get_filtered_pull_requests(self, pull_requests):
        '''
        This method fetches missing params for PR and filter them
        by specified options. It include add all PR's with labels
        from options.include_labels array
        And exclude all from options.exclude_labels array.

        @return [Array] filtered PR's
        '''

        pull_requests = self.filter_array_by_labels(pull_requests)
        pull_requests = self.filter_merged_pull_requests(pull_requests)
        if self.options.verbose:
            print("Filtered pull requests: {0}".format(len(pull_requests)))
        return pull_requests

    def filter_merged_pull_requests(self, pull_requests):
        '''
        This method filter only merged PR and
        fetch missing required attributes for pull requests:
        "merged_at" - is a date, when issue PR was merged.
        More correct to use merged date, rather than closed date.
        '''

        if self.options.verbose:
            print("Fetching merged dates...")
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
                # TODO: not sure if i do the right thing
                pulls.remove(pr)
        return pulls

    def fetch_and_filter_tags(self):
        ''' fetch, filter tags, fetch dates and sort them in time order. '''

        self.all_tags = self.fetcher.get_all_tags()
        self.filtered_tags = self.get_filtered_tags(self.all_tags)
        self.fetch_tags_dates()

    def sort_tags_by_date(self, tags):
        ''' Sort all tags by date. '''

        if self.options.verbose:
            print("Sorting tags...")
        tags.sort(key=lambda x: self.get_time_of_tag(x))
        tags.reverse()
        return tags

    def get_time_of_tag(self, tag):
        '''
        Try to find tag date in local hash.
        Otherwise fFetch tag time and put it to local hash file.

        @param [Hash] tag name of the tag
        @return [Time] time of specified tag
        '''

        if not tag:
            raise ChangelogGeneratorError("tag is nil")

        name_of_tag = tag["name"]
        time_for_name = self.tag_times_dict.get(name_of_tag, None)
        if time_for_name:
            return time_for_name
        else:
            time_string = self.fetcher.fetch_date_of_tag(tag)
            try:
                self.tag_times_dict[name_of_tag] = dt_parser(time_string)
            except UnicodeWarning:
                print(tag)
                self.tag_times_dict[name_of_tag] = dt_parser(time_string)
            return self.tag_times_dict[name_of_tag]

    def detect_link_tag_time(self, newer_tag):
        ''' Detect link, name and time for specified tag.

        @param [Hash] newer_tag newer tag. Can be nil,
                                if it's Unreleased section.
        @return [Array] link, name and time of the tag
        '''

        # if tag is nil - set current time
        newer_tag_time = self.get_time_of_tag(newer_tag) if newer_tag \
            else datetime.datetime.now()

        # if it's future release tag - set this value
        if newer_tag["name"] == self.options.unreleased_label and self.options.future_release:
            newer_tag_name = self.options.future_release
            newer_tag_link = self.options.future_release
        else:
            # put unreleased label if there is no name for the tag
            newer_tag_name = newer_tag["name"] if newer_tag \
                else self.options.unreleased_label
            newer_tag_link = newer_tag_name if newer_tag else "HEAD"
        return [newer_tag_link, newer_tag_name, newer_tag_time]

    def detect_since_tag(self):
        '''
        @return [Object] try to find newest tag using Reader()
        and options.base if specified, otherwise returns nil
        '''
        return self.options.since_tag or self.version_of_first_item()

    def version_of_first_item(self):
        try:
            sections = read_changelog(self.options.base)
            return sections[0]["version"]
        except(IOError, TypeError):
            self.get_temp_tag_for_repo_creation()

    def get_temp_tag_for_repo_creation(self):
        tag_date = self.tag_times_dict.get(REPO_CREATED_KEY, None)
        if not tag_date:
            tag_name, tag_date = self.fetcher.get_first_event_date()
            self.tag_times_dict[tag_name] = dt_parser(tag_date)
        return REPO_CREATED_KEY

    def get_filtered_tags(self, all_tags):
        '''
        Return tags after filtering tags in lists provided by
        option: --between-tags & --exclude-tags

        @return [Array]
        '''

        filtered_tags = self.filter_since_tag(all_tags)
        if self.options.between_tags:
            filtered_tags = self.filter_between_tags(filtered_tags)
        if self.options.due_tag:
            filtered_tags = self.filter_due_tag(filtered_tags)
        return self.filter_excluded_tags(filtered_tags)

    def filter_since_tag(self, all_tags):
        '''
        @param [Array] all_tags all tags
        @return [Array] filtered tags according :since_tag option
        '''

        tag = self.detect_since_tag()
        if not tag or tag == REPO_CREATED_KEY:
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
        '''
        @param [Array] all_tags all tags
        @return [Array] filtered tags according due_tag option
        '''

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
        '''
        @param [Array] all_tags all tags
        @return [Array] filtered tags according :between_tags option
        '''

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
        '''
        @param [Array] all_tags all tags
        @return [Array] filtered tags according exclude_tags or
                        exclude_tags_regex option
        '''

        if self.options.exclude_tags:
            return self.apply_exclude_tags(all_tags)
        elif self.options.exclude_tags_regex:
            return self.apply_exclude_tags_regex(all_tags)
        return all_tags

    def apply_exclude_tags(self, all_tags):
        return self.filter_exact_tags(all_tags)

    def apply_exclude_tags_regex(self, all_tags):
        return self.filter_tags_with_regex(
            all_tags, self.options.exclude_tags_regex)

    def filter_tags_with_regex(self, all_tags, regex):
        filtered = []
        for tag in all_tags:
            if not re.match(regex, tag["name"]):
                filtered.append(tag)
        if len(all_tags) == len(filtered):
            self.warn_if_nonmatching_regex()
        return filtered

    def filter_exact_tags(self, all_tags):
        filtered = copy.deepcopy(all_tags)
        for tag in all_tags:
            if tag["name"] not in self.options.exclude_tags:
                self.warn_if_tag_not_found(tag, "exclude-tags")
            else:
                filtered.remove(tag)
        return filtered

    def warn_if_nonmatching_regex(self):
        print("WARNING: unable to reject any tag, using regex "
            "'{0}' in --exclude-tags-regex option.".format(
                self.options.exclude_tags_regex))

    def warn_if_tag_not_found(self, tag, option):
        print("WARNING: can't find tag '{0}' specified with "
            "--{1} option.".format(tag, option))

