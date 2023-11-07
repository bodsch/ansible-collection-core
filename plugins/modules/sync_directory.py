#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule

import os
import logging
import collections
import re
import dirsync

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: sync_directory
version_added: 1.1.3
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Syncronises directories similar to rsync.

description:
    - Syncronises directories similar to rsync.

options:
  source_directory:
    description:
      - The source directory.
    type: str
    default: ""
    required: true
  destination_directory:
    description:
      - The destination directory.
    type: str
    default: ""
    required: true
  arguments:
    description:
      - a dictionary with custom arguments.
    type: dict
    required: false
  include_pattern:
    description:
      - a list with regex patterns to include.
    type: list
    required: false
  exclude_pattern:
    description:
      - a list with regex patterns to exclude.
    type: list
    required: false
"""

EXAMPLES = r"""
- name: sync /opt/server/data to /opt/data
  bodsch.core.sync_directory:
    source_directory: /opt/server/data
    destination_directory: /opt/data
    arguments:
      verbose: true
      purge: false
"""

RETURN = r"""
changed:
    description:
        - changed or not
    type: bool
msg:
    description:
        - statusinformation
    type: string
"""

# ---------------------------------------------------------------------------------------


class TailLogHandler(logging.Handler):

    def __init__(self, log_queue):
        logging.Handler.__init__(self)
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.append(self.format(record))


class TailLogger(object):

    def __init__(self, maxlen):
        self._log_queue = collections.deque(maxlen=maxlen)
        self._log_handler = TailLogHandler(self._log_queue)

    def contents(self):
        return '\n'.join(self._log_queue)

    @property
    def log_handler(self):
        return self._log_handler


class Sync(object):
    """
    """

    def __init__(self, module):
        """
        """
        self.module = module

        self.source_directory = module.params.get("source_directory")
        self.destination_directory = module.params.get("destination_directory")

        self.arguments = module.params.get("arguments")

        self.include_pattern = module.params.get("include_pattern")
        self.exclude_pattern = module.params.get("exclude_pattern")

    def run(self):
        """
        """
        _failed = False
        _changed = False
        _msg = "The directory are synchronous."

        include_pattern = None
        exclude_pattern = None

        tail = TailLogger(2)

        logger = logging.getLogger('dirsync')
        formatter = logging.Formatter('%(message)s')

        log_handler = tail.log_handler
        log_handler.setFormatter(formatter)
        logger.addHandler(log_handler)
        logger.setLevel(logging.DEBUG)

        if self.include_pattern and len(self.include_pattern) > 0:
            include_pattern = "|".join(self.include_pattern)
            include_pattern = f".*({include_pattern}).*"

        if self.exclude_pattern and len(self.exclude_pattern) > 0:
            exclude_pattern = "|".join(self.exclude_pattern)
            exclude_pattern = f".*({exclude_pattern}).*"

        # self.module.log(msg=f"include_pattern: {include_pattern}")
        # include_pattern = ('^.*\\.json$',)

        if not os.path.isdir(self.source_directory):
            return dict(
                failed=True,
                msg="The source directory does not exist."
            )

        if not os.path.isdir(self.destination_directory):
            return dict(
                failed=True,
                msg="The destination directory does not exist."
            )

        if self.arguments and isinstance(self.arguments, dict):
            _create = self.arguments.get("create", False)
            _verbose = self.arguments.get("verbose", False)
            _purge = self.arguments.get("purge", False)

            args = dict(
                create=_create,
                verbose=_verbose,
                purge=_purge,
            )

            args.update({'logger': logger})

        else:
            args = {
                'create': 'False',
                'verbose': 'False',
                'purge': 'False',
                'logger': logger,
            }

        if include_pattern:
            args.update({'include': include_pattern, })
        if exclude_pattern:
            args.update({'exclude': exclude_pattern, })

        args.update({'force': True})

        self.module.log(msg=f"args: {args}")

        dirsync.sync(self.source_directory, self.destination_directory, 'sync', **args)

        log_contents = tail.contents()

        self.module.log(msg=f"log_contents: {log_contents}")

        if len(log_contents) > 0:
            if "directories were created" in log_contents:
                pattern = re.compile(r"(?P<directories>\d+).*directories were created.$")
            else:
                pattern = re.compile(r"(?P<directories>\d+).*directories parsed, (?P<files_copied>\d+) files copied")

            re_result = re.search(pattern, log_contents)

            if re_result:

                directories = None
                files_copied = None

                try:
                    directories = re_result.group('directories')
                except Exception:
                    pass

                try:
                    files_copied = re_result.group('files_copied')
                except Exception:
                    pass

                # self.module.log(msg=f"directories: {directories}")
                # self.module.log(msg=f"files_copied: {files_copied}")

                if files_copied:
                    if int(files_copied) == 0:
                        _changed = False
                        _msg = "The directory are synchronous."
                    elif int(files_copied) > 0:
                        _changed = True
                        _msg = "The directory were successfully synchronised."
                elif directories:
                    if int(directories) > 0:
                        _changed = True
                        _msg = "The directory were successfully synchronised."

        result = dict(
            changed=_changed,
            failed=_failed,
            msg=_msg
        )

        return result


def main():
    """
    """
    args = dict(
        source_directory=dict(
            required=True,
            type='str'
        ),
        destination_directory=dict(
            required=True,
            type='str'
        ),
        arguments=dict(
            required=False,
            type='dict'
        ),
        include_pattern=dict(
            required=False,
            type='list'
        ),
        exclude_pattern=dict(
            required=False,
            type='list'
        ),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    p = Sync(module)
    result = p.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == '__main__':
    main()
