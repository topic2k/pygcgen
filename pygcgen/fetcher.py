# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import os
import re
import sys
import subprocess
import threading
if sys.version_info.major == 3:
    from builtins import object, range

from agithub.GitHub import GitHub

from .pygcgen_exceptions import GithubApiError


GH_CFG_VARS = ["github.pygcgen.token", "github.token"]
PER_PAGE_NUMBER = 100
CHANGELOG_GITHUB_TOKEN = "CHANGELOG_GITHUB_TOKEN"
GH_RATE_LIMIT_EXCEEDED_MSG = \
    "GitHub API rate limit exceeded, change log may be missing some issues. " \
    "Please provide a token with -t option or in git config."
NO_TOKEN_PROVIDED = \
    "Warning: No token provided. Neither -t option, git config or variable " \
    "$CHANGELOG_GITHUB_TOKEN found. This script can make only " \
    "50 requests to GitHub API per hour without token!"
REPO_CREATED_TAG_NAME = "repo_created_at"


class Fetcher(object):
    """
    A Fetcher is responsible for all requests to GitHub and all basic
    manipulation with related data (such as filtering, validating, e.t.c).
    """

    def __init__(self, options):
        self.options = options
        self.first_issue = None
        self.events_cnt = 0
        self.fetch_github_token()
        if isinstance(self.options.user, bytes):
            self.options.user = self.options.user.decode("utf8")
        if isinstance(self.options.project, bytes):
            self.options.project = self.options.project.decode("utf8")
        if isinstance(self.options.token, bytes):
            self.options.token = self.options.token.decode("utf8")
        if options.token:
            self.github = GitHub(
                token=options.token,
                api_url=options.github_endpoint
            )
        else:
            self.github = GitHub(api_url=options.github_endpoint)

    def fetch_github_token(self):
        """
        Fetch GitHub token. First try to use variable provided
        by --token option, otherwise try to fetch it from git config
        and last CHANGELOG_GITHUB_TOKEN env variable.

        :returns: Nothing
        """

        if not self.options.token:
            try:
                for v in GH_CFG_VARS:
                    cmd = ['git', 'config', '--get', '{0}'.format(v)]
                    self.options.token = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE).communicate()[0].strip()
                    if self.options.token:
                        break
            except (subprocess.CalledProcessError, WindowsError):
                pass
        if not self.options.token:
            self.options.token = os.environ.get(CHANGELOG_GITHUB_TOKEN)
        if not self.options.token:
            print(NO_TOKEN_PROVIDED)

    def get_all_tags(self):
        """
        Fetch all tags for repository from Github.

        :return: tags in repository
        :rtype: list
        """

        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        if verbose:
            print("Fetching tags...")

        tags = []
        page = 1
        while page > 0:
            if verbose > 2:
                print(".", end="")
            rc, data = gh.repos[user][repo].tags.get(
                page=page, per_page=PER_PAGE_NUMBER)
            if rc == 200:
                tags.extend(data)
            else:
                self.raise_GitHubError(rc, data, gh.getheaders())
            page = NextPage(gh)
        if verbose > 2:
            print(".")

        if len(tags) == 0:
            if not self.options.quiet:
                print("Warning: Can't find any tags in repo. Make sure, that "
                      "you push tags to remote repo via 'git push --tags'")
                exit()
        if verbose > 1:
            print("Found {} tag(s)".format(len(tags)))
        return tags

    def fetch_closed_issues_and_pr(self):
        """
        This method fetches all closed issues and separate them to
        pull requests and pure issues (pull request is kind of issue
        in term of GitHub).

        :rtype: list, list
        :return: issues, pull-requests
        """

        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        if verbose:
            print("Fetching closed issues and pull requests...")

        data = []
        issues = []
        data = []
        page = 1
        while page > 0:
            if verbose > 2:
                print(".", end="")
            rc, data = gh.repos[user][repo].issues.get(
                page=page, per_page=PER_PAGE_NUMBER,
                state='closed', filter='all'
            )
            if rc == 200:
                issues.extend(data)
            else:
                self.raise_GitHubError(rc, data, gh.getheaders())
            if len(issues) >= self.options.max_issues:
                break
            page = NextPage(gh)
        self.first_issue = data[-1] if len(data) > 0 else []
        if verbose > 2:
            print(".")

        # separate arrays of issues and pull requests:
        prs = []
        iss = []
        for i in issues:
            if "pull_request" in i:
                prs.append(i)
            else:
                iss.append(i)
        if verbose > 1:
            print("\treceived {} issues and  {} pull requests.".format(
                len(iss), len(prs))
            )
        return iss, prs

    def fetch_closed_pull_requests(self):
        """
        Fetch all pull requests. We need them to detect "merged_at" parameter

        :rtype: list
        :return: all pull requests
        """

        pull_requests = []
        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        if verbose:
            print("Fetching closed pull requests...")
        page = 1
        while page > 0:
            if verbose > 2:
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
                self.raise_GitHubError(rc, data, gh.getheaders())
            page = NextPage(gh)
        if verbose > 2:
            print(".")
        if verbose > 1:
            print("\tfetched {} closed pull requests.".format(
                len(pull_requests))
            )
        return pull_requests

    def fetch_repo_creation_date(self):
        """
        Get the creation date of the repository from GitHub.

        :rtype: str, str
        :return: special tag name, creation date as ISO date string
        """
        gh = self.github
        user = self.options.user
        repo = self.options.project
        rc, data = gh.repos[user][repo].get()
        if rc == 200:
            return REPO_CREATED_TAG_NAME, data["created_at"]
        else:
            self.raise_GitHubError(rc, data, gh.getheaders())
        return None, None

    def fetch_events_async(self, issues, tag_name):
        """
        Fetch events for all issues and add them to self.events

        :param list issues: all issues
        :param str tag_name: name of the tag to fetch events for
        :returns: Nothing
        """

        if not issues:
            return issues

        max_simultaneous_requests = self.options.max_simultaneous_requests
        verbose = self.options.verbose
        gh = self.github
        user = self.options.user
        repo = self.options.project
        self.events_cnt = 0
        if verbose:
            print("fetching events for {} {}... ".format(
                len(issues), tag_name)
            )

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
                    self.raise_GitHubError(rc, data, gh.getheaders())
                page = NextPage(gh)

        threads = []
        cnt = len(issues)
        for i in range(0, (cnt // max_simultaneous_requests) + 1):
            for j in range(max_simultaneous_requests):
                idx = i * max_simultaneous_requests + j
                if idx == cnt:
                    break
                t = threading.Thread(target=worker, args=(issues[idx],))
                threads.append(t)
                t.start()
                if verbose > 2:
                    print(".", end="")
                    if not idx % PER_PAGE_NUMBER:
                        print("")
            for t in threads:
                t.join()
        if verbose > 2:
            print(".")

    def fetch_date_of_tag(self, tag):
        """
        Fetch time for tag from repository.

        :param dict tag: dictionary with tag information
        :rtype: str
        :return: time of specified tag as ISO date string
        """

        if self.options.verbose > 1:
            print("\tFetching date for tag {}".format(tag["name"]))
        gh = self.github
        user = self.options.user
        repo = self.options.project

        rc, data = gh.repos[user][repo].git.commits[
            tag["commit"]["sha"]].get()
        if rc == 200:
            return data["committer"]["date"]
        self.raise_GitHubError(rc, data, gh.getheaders())

    def fetch_commit(self, event):
        """
        Fetch commit data for specified event.

        :param dict event: dictionary with event information
        :rtype: dict
        :return: dictionary with commit data
        """

        gh = self.github
        user = self.options.user
        repo = self.options.project

        rc, data = gh.repos[user][repo].git.commits[
            event["commit_id"]].get()
        if rc == 200:
            return data
        self.raise_GitHubError(rc, data, gh.getheaders())

    @staticmethod
    def raise_GitHubError(rc, data, header):
        hdr = dict(header)
        if rc == 403 and hdr.get("x-ratelimit-remaining") == '0':
            # TODO: add auto-retry
            raise GithubApiError(GH_RATE_LIMIT_EXCEEDED_MSG)
        raise GithubApiError("({0}) {1}".format(rc, data["message"]))


def NextPage(gh):
    """
    Checks if a GitHub call returned multiple pages of data.

    :param gh: GitHub() instance
    :rtype: int
    :return: number of next page or 0 if no next page
    """
    header = dict(gh.getheaders())
    if 'Link' in header:
        parts = header['Link'].split(',')
        for part in parts:
            subparts = part.split(';')
            sub = subparts[1].split('=')
            if sub[0].strip() == 'rel':
                if sub[1] == '"next"':
                    page = int(
                        re.match(
                            r'.*page=(\d+).*', subparts[0],
                            re.IGNORECASE | re.DOTALL | re.UNICODE
                        ).groups()[0]
                    )
                    return page
    return 0
