# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import re
import subprocess
import threading
from agithub.GitHub import GitHub

from pygcgen_exceptions import GithubApiError


GH_CFG_VARS = ["github.pygcgen.token", "github.token"]
PER_PAGE_NUMBER = 100
MAX_SIMULTANEOUS_REQUESTS = 25
CHANGELOG_GITHUB_TOKEN = "CHANGELOG_GITHUB_TOKEN"
GH_RATE_LIMIT_EXCEEDED_MSG = \
    "GitHub API rate limit exceeded, change log may be missing some issues. " \
    "Please provide a token with -t option or in git config."
NO_TOKEN_PROVIDED = \
    "Warning: No token provided. Neither -t option, git config or variable " \
    "$CHANGELOG_GITHUB_TOKEN was not found. This script can make only " \
    "50 requests to GitHub API per hour without token!"


class Fetcher:
    '''
    A Fetcher is responsible for all requests to GitHub and all basic
    manipulation with related data (such as filtering, validating, e.t.c).
    '''

    def __init__(self, options):
        self.options = options
        self.fetch_github_token()
        if options.token:
            self.github = GitHub(
                token=options.token,
                api_url=options.github_endpoint
            )
        else:
            self.github = GitHub(api_url=options.github_endpoint)

    def fetch_github_token(self):
        '''
        Returns GitHub token. First try to use variable provided
        by --token option, otherwise try to fetch it from git config
        and last CHANGELOG_GITHUB_TOKEN env variable.

        @return [String]
        '''

        if not self.options.token:
            try:
                for v in GH_CFG_VARS:
                    cmd = ['git', 'config', '--get', '{0}'.format(v)]
                    self.options.token = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE).communicate()[0].strip()
                    if self.options.token:
                        break
            except subprocess.CalledProcessError:
                pass
        if not self.options.token:
            self.options.token = os.environ.get(CHANGELOG_GITHUB_TOKEN)
        if not self.options.token:
            print(NO_TOKEN_PROVIDED)

    def get_all_tags(self):
        '''
        Fill input array with tags.

        @return [Array] array of tags in repo
        '''

        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        if verbose:
            print("Fetching tags..")

        tags = []
        page = 1
        while page > 0:
            if verbose:
                print(".", end="")
            rc, data = gh.repos[user][repo].tags.get(
                page=page, per_page=PER_PAGE_NUMBER)
            if rc == 200:
                tags.extend(data)
            else:
                self.check_returncode(rc, data, gh.getheaders())
            page = NextPage(gh)
        if self.options.verbose:
            print(".")

        if len(tags) == 0:
            print("Warning: Can't find any tags in repo. Make sure, "
                  "that you push tags to remote repo via 'git push --tags'")
        elif verbose:
            print("Found {0} tag(s)".format(len(tags)))
        return tags

    def fetch_closed_issues_and_pr(self):
        '''
        This method fetch all closed issues and separate them to
        pull requests and pure issues (pull request is kind of issue
        in term of GitHub).

        @return [Tuple] with (issues, pull-requests)
        '''

        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        if verbose:
            print("Fetching closed issues and pull requests..")

        issues = []
        page = 1
        while page > 0:
            if verbose:
                print(".", end="")
            rc, data = gh.repos[user][repo].issues.get(
                page=page, per_page=PER_PAGE_NUMBER,
                state='closed', filter='all'
            )
            if rc == 200:
                issues.extend(data)
            else:
                self.check_returncode(rc, data, gh.getheaders())
            if len(issues) >= self.options.max_issues:
                break
            page = NextPage(gh)
        self.first_issue = data[-1] if len(data) > 0 else []
        if verbose:
            print(".")
            print("Received: {0}".format(len(issues)))

        # separate arrays of issues and pull requests:
        prs = []
        iss = []
        for i in issues:
            if "pull_request" in i:
                prs.append(i)
            else:
                iss.append(i)
        return iss, prs

    def fetch_closed_pull_requests(self):
        '''
        Fetch all pull requests. We need them to detect "merged_at" parameter

        @return [Array] all pull requests
        '''

        pull_requests = []
        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        if verbose:
            print("Fetching closed pull requests..")
        page = 1
        while page > 0:
            if verbose:
                print(".", end="")

            if self.options.release_branch:
                rc, data = gh.repos[user][repo].pulls.get(
                    page=page, per_page=PER_PAGE_NUMBER, state='closed',
                    base=self.options.release_branch
                )
            else:
                rc, data = gh.repos[user][repo].pulls.get(
                    page=page, per_page=PER_PAGE_NUMBER, state='closed',
                )

            if rc == 200:
                pull_requests.extend(data)
            else:
                self.check_returncode(rc, data, gh.getheaders())
            page = NextPage(gh)
        if verbose:
            print(".")
            print("Fetched closed pull requests: {0}".format(len(pull_requests)))
        return pull_requests

    def get_first_event_date(self):
        gh = self.github
        user = self.options.user
        repo = self.options.project
        rc, data = gh.repos[user][repo].get()
        if rc == 200:
            tag_name = "repo_created_at"
            tag_date = data["created_at"]
            return tag_name, tag_date
        else:
            self.check_returncode(rc, data, gh.getheaders())
        return None, None

    def fetch_events_async(self, issues, label):
        '''
        Fetch events for all issues and add them to self.events

        @param [Array] issues
        '''
        if not issues:
            return issues
        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        self.events_cnt = 0
        if verbose:
            print("events for {0} (async)... ".format(label))

        def worker(issue):
            page = 1
            issue['events'] = []
            while page > 0:
                rc, data = gh.repos[user][repo].issues[
                    issue['number']].events.get(
                    page=page, per_page=PER_PAGE_NUMBER)
                if rc == 200:
                    issue['events'].extend(data)
                    self.events_cnt += len(data)
                else:
                    self.check_returncode(rc, data, gh.getheaders())
                page = NextPage(gh)

        threads = []
        cnt = len(issues)
        for i in range(0, (cnt / MAX_SIMULTANEOUS_REQUESTS) + 1):
            for j in range(MAX_SIMULTANEOUS_REQUESTS):
                idx = i * MAX_SIMULTANEOUS_REQUESTS + j
                if idx == cnt:
                    break
                t = threading.Thread(target=worker, args=(issues[idx],))
                threads.append(t)
                t.start()
                if verbose:
                    print(".", end="")
                    if not idx % PER_PAGE_NUMBER:
                        print("")
            for t in threads:
                t.join()
        if verbose:
            print(".")

    def fetch_date_of_tag(self, tag):
        '''Fetch tag time from repo

        @param [Hash] tag
        @return [Time] time of specified tag
        '''

        if self.options.verbose:
            print("Fetching date for tag {0}".format(tag["name"]))
        gh = self.github
        user = self.options.user
        repo = self.options.project

        rc, data = gh.repos[user][repo].git.commits[
            tag["commit"]["sha"]].get()
        if rc == 200:
            time_string = data["committer"]["date"]
            return time_string
        else:
            self.check_returncode(rc, data, gh.getheaders())
        return None

    def fetch_commit(self, event):
        '''
        Fetch commit for specified event
        @return [Hash]
        '''
        gh = self.github
        user = self.options.user
        repo = self.options.project

        rc, data = gh.repos[user][repo].git.commits[
            event["commit_id"]].get()
        if rc == 200:
            return data
        else:
            self.check_returncode(rc, data, gh.getheaders())
        return None

    def check_returncode(self, rc, data, header):
        hdr =dict(header)
        if rc == 403 and hdr.get("x-ratelimit-remaining") == '0':
            raise GithubApiError(GH_RATE_LIMIT_EXCEEDED_MSG)
        raise GithubApiError("({0}) {1}".format(rc, data["message"]))


def NextPage(gh):
    header = dict(gh.getheaders())
    if 'link' in header:
        parts = header['link'].split(',')
        for part in parts:
            subparts = part.split(';')
            sub = subparts[1].split('=')
            if sub[0].strip() == 'rel':
                if sub[1] == '"next"':
                    page = int(re.match(ur'.*page=(\d+).*',
                               subparts[0],
                               re.IGNORECASE | re.DOTALL | re.UNICODE).
                               groups()[0])
                    return page
    return 0
