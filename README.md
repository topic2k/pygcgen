# pygcgen

Automaticaly generate a changelog based on GitHub issues and pull requests. For each tag there will be a section with closed issues and merged pull requests. Also there can be user defined sections based on labels.

## Status

[![PyPI Python Version](https://img.shields.io/pypi/pyversions/pygcgen.svg)](https://pypi.python.org/pypi/pygcgen)
[![PyPI Version](https://img.shields.io/pypi/v/pygcgen.svg)](https://pypi.python.org/pypi/pygcgen)
[![PyPI Status](https://img.shields.io/pypi/status/pygcgen.svg)](https://pypi.python.org/pypi/pygcgen)
[![Travis Build Status](https://travis-ci.org/topic2k/pygcgen.svg?branch=master)](https://travis-ci.org/topic2k/pygcgen)
[![Code Climate Status](https://codeclimate.com/github/topic2k/pygcgen/badges/gpa.svg)](https://codeclimate.com/github/topic2k/pygcgen)
[![Code Climate Issue Count](https://codeclimate.com/github/topic2k/pygcgen/badges/issue_count.svg)](https://codeclimate.com/github/topic2k/pygcgen/issues)
[![Test Coverage](https://codeclimate.com/github/topic2k/pygcgen/badges/coverage.svg)](https://codeclimate.com/github/topic2k/pygcgen/coverage)
[![RTD Documentation Status](https://readthedocs.org/projects/pygcgen/badge/?version=latest)](http://pygcgen.readthedocs.io/en/latest/?badge=latest)

## Installation

pygcgen is available on [PyPi](https://pypi.python.org/pypi/pygcgen):
`pip install pygcgen`
or from [source](https://github.com/topic2k/pygcgen/archive/master.zip):
`python setup.py install`

A command line tool will be installed into the python/Scripts path.


## Usage

In your repository root dir: `pygcgen` or `python -m pygcgen`.
From elsewhere: `pygcgen --user topic2k --project pygcgen` or `pygcgen -u topic2k -p pygcgen`.


|Info
|-
|GitHub has a [rate limit](https://developer.github.com/v3/#rate-limiting). Unauthenticated requests are limited to 60 requests per hour. To make authenticated requests, provide a token with `--token <your-40-digit-token>` or `-t <your-40-digit-token>`


## Example output

pygcgen's own changelog is generated with itself: [CHANGELOG.md](https://github.com/topic2k/pygcgen/blob/master/CHANGELOG.md)




## Credit

pygcgen was born as a conversion from Ruby to Python of [skywinder's](https://github.com/skywinder) [GitHub Changelog Generator](https://github.com/skywinder/github-changelog-generator/tree/9483c5edcb6365698c7beebf819d86c1f7e5aeeb)
