.. |br| raw:: html

   <br />

About
-----

Automaticaly generate a changelog based on GitHub issues and pull requests. For each tag there will be a section with closed issues and merged pull requests. Also there can be user defined sections based on labels.

Status
------

.. image:: https://img.shields.io/pypi/pyversions/pygcgen.svg
    :target: https://pypi.python.org/pypi/pygcgen

.. image:: https://img.shields.io/pypi/v/pygcgen.svg
    :target: https://pypi.python.org/pypi/pygcgen

.. image:: https://img.shields.io/pypi/status/pygcgen.svg
    :target: https://pypi.python.org/pypi/pygcgen

.. image:: https://travis-ci.org/topic2k/pygcgen.svg?branch=master
    :target: https://travis-ci.org/topic2k/pygcgen

.. image:: https://codeclimate.com/github/topic2k/pygcgen/badges/gpa.svg
   :target: https://codeclimate.com/github/topic2k/pygcgen
   :alt: Code Climate

.. image:: https://codeclimate.com/github/topic2k/pygcgen/badges/issue_count.svg
   :target: https://codeclimate.com/github/topic2k/pygcgen
   :alt: Issue Count

.. image:: https://codeclimate.com/github/topic2k/pygcgen/badges/coverage.svg
   :target: https://codeclimate.com/github/topic2k/pygcgen/coverage
   :alt: Test Coverage

.. image:: https://readthedocs.org/projects/pygcgen/badge/?version=latest
   :target: http://pygcgen.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status


Installation
------------

pygcgen is available on `PyPi <https://pypi.python.org/pypi/pygcgen>`_:
:code:`pip install pygcgen`
|br|
or from `source <https://github.com/topic2k/pygcgen/archive/master.zip>`_:
:code:`python setup.py install`

A command line tool will be installed into the python/Scripts path.



Usage
-----

In your repository root dir: :code:`pygcgen` or :code:`python -m pygcgen`.
|br|
From elsewhere: :code:`pygcgen --user topic2k --project pygcgen` or :code:`pygcgen -u topic2k -p pygcgen`.



.. note:: GitHub has a `rate limit <https://developer.github.com/v3/#rate-limiting>`_.
          Unauthenticated requests are limited to 60 requests per hour. To make authenticated
          requests, provide a token with :code:`--token <your-40-digit-token>` or :code:`-t <your-40-digit-token>`.



Example output
--------------

pygcgen's own changelog is generated with itself:
`CHANGELOG.md <https://github.com/topic2k/pygcgen/blob/master/CHANGELOG.md>`_



Credit
------

pygcgen was born as a conversion from Ruby to Python of
`skywinder's <https://github.com/skywinder>`_
`GitHub Changelog Generator <https://github.com/skywinder/github-changelog-generator/tree/9483c5edcb6365698c7beebf819d86c1f7e5aeeb>`_

