#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Ansible module to synchronize directories using the dirsync library.

This module synchronizes a source directory to a destination directory in a
manner comparable to a simplified rsync workflow. It supports optional include
and exclude regex filters and allows selected dirsync runtime flags to be
passed through the ``arguments`` parameter.
"""

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import collections
import logging
import os
import re
from typing import Any, Deque, Dict, List, Optional, Pattern, Tuple

import dirsync
from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: sync_directory
version_added: "1.1.3"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Synchronize directories in a way similar to rsync.

description:
  - Synchronize a source directory to a destination directory by using the
    Python C(dirsync) library.
  - Supports optional include and exclude regex filters.
  - Supports a subset of dirsync runtime options via the O(arguments) parameter.

requirements:
  - dirsync

notes:
  - The module supports check mode.
  - In check mode, the module validates input and skips the actual sync operation.
  - The source and destination directories must already exist.

options:
  source_directory:
    description:
      - Source directory that should be synchronized.
    type: path
    required: true

  destination_directory:
    description:
      - Destination directory that should receive synchronized content.
    type: path
    required: true

  arguments:
    description:
      - Dictionary with selected dirsync runtime options.
    type: dict
    required: false
    suboptions:
      create:
        description:
          - Allow dirsync to create missing directories in the destination.
        type: bool
        required: false
      verbose:
        description:
          - Enable verbose dirsync logging.
        type: bool
        required: false
      purge:
        description:
          - Remove files from the destination that no longer exist in the source.
        type: bool
        required: false

  include_pattern:
    description:
      - List of regex fragments used to include matching paths.
      - The fragments are combined into a single regex passed to dirsync.
    type: list
    elements: str
    required: false

  exclude_pattern:
    description:
      - List of regex fragments used to exclude matching paths.
      - The fragments are combined into a single regex passed to dirsync.
    type: list
    elements: str
    required: false
"""

EXAMPLES = r"""
- name: Synchronize /opt/server/data to /opt/data
  bodsch.core.sync_directory:
    source_directory: /opt/server/data
    destination_directory: /opt/data
    arguments:
      verbose: true
      purge: false

- name: Synchronize only JSON files
  bodsch.core.sync_directory:
    source_directory: /opt/server/data
    destination_directory: /opt/data
    include_pattern:
      - '\.json$'

- name: Exclude cache and temporary files
  bodsch.core.sync_directory:
    source_directory: /opt/server/data
    destination_directory: /opt/data
    exclude_pattern:
      - '/cache/'
      - '\.tmp$'

- name: Validate sync parameters in check mode
  bodsch.core.sync_directory:
    source_directory: /opt/server/data
    destination_directory: /opt/data
  check_mode: true
"""

RETURN = r"""
changed:
  description:
    - Indicates whether synchronization changed the destination directory.
  returned: always
  type: bool
  sample: true

failed:
  description:
    - Indicates whether the module execution failed.
  returned: always
  type: bool
  sample: false

msg:
  description:
    - Human-readable module status message.
  returned: always
  type: str
  sample: "The directories were successfully synchronized."
"""

# ---------------------------------------------------------------------------------------


class TailLogHandler(logging.Handler):
    """
    Logging handler that stores formatted log records in a bounded queue.
    """

    def __init__(self, log_queue: Deque[str]) -> None:
        """
        Initialize the handler with a queue that receives formatted log messages.

        Args:
            log_queue: Bounded queue used to store log lines.
        """
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        """
        Append the formatted log record to the internal queue.

        Args:
            record: Log record emitted by the logger.
        """
        self.log_queue.append(self.format(record))


class TailLogger(object):
    """
    Small helper that captures the last N log lines from a logger.
    """

    def __init__(self, maxlen: int) -> None:
        """
        Create a bounded in-memory log buffer.

        Args:
            maxlen: Maximum number of log lines to retain.
        """
        self._log_queue: Deque[str] = collections.deque(maxlen=maxlen)
        self._log_handler = TailLogHandler(self._log_queue)

    def contents(self) -> str:
        """
        Return all buffered log lines as a single string.

        Returns:
            str: Joined log output separated by newlines.
        """
        return "\n".join(self._log_queue)

    @property
    def log_handler(self) -> TailLogHandler:
        """
        Return the logging handler used to capture log messages.

        Returns:
            TailLogHandler: Handler instance connected to the internal queue.
        """
        return self._log_handler


class Sync(object):
    """
    Synchronize two directories by using the dirsync library.

    The public API of the class is intentionally small. Parameter parsing and
    synchronization orchestration are exposed through C(run()), while internal
    helpers handle logger setup, pattern normalization, argument construction,
    and result parsing.
    """

    _DIRECTORIES_CREATED_PATTERN: Pattern[str] = re.compile(
        r"(?P<directories>\d+).*directories were created\.$"
    )
    _FILES_COPIED_PATTERN: Pattern[str] = re.compile(
        r"(?P<directories>\d+).*directories parsed,\s*(?P<files_copied>\d+) files copied"
    )

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the sync wrapper from the Ansible module parameters.

        Args:
            module: Active Ansible module instance.
        """
        self.module = module

        self.source_directory: str = module.params.get("source_directory")
        self.destination_directory: str = module.params.get("destination_directory")
        self.arguments: Optional[Dict[str, Any]] = module.params.get("arguments")
        self.include_pattern: Optional[List[str]] = module.params.get("include_pattern")
        self.exclude_pattern: Optional[List[str]] = module.params.get("exclude_pattern")

    def run(self) -> Dict[str, Any]:
        """
        Execute the directory synchronization workflow.

        Returns:
            dict: Result dictionary containing C(changed), C(failed), and C(msg).
        """
        failed = False
        changed = False
        msg = "The directories are already synchronized."

        validation_error = self._validate_directories()
        if validation_error is not None:
            return validation_error

        if self.module.check_mode:
            return {
                "failed": False,
                "changed": False,
                "msg": "Check mode: synchronization was not executed.",
            }

        include_pattern = self._build_filter_pattern(self.include_pattern)
        exclude_pattern = self._build_filter_pattern(self.exclude_pattern)

        tail = TailLogger(10)
        logger = logging.getLogger("dirsync")
        handler = tail.log_handler
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        previous_level = logger.level
        previous_propagate = logger.propagate

        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        try:
            args = self._build_dsync_args(
                logger=logger,
                include_pattern=include_pattern,
                exclude_pattern=exclude_pattern,
            )

            self.module.log(msg=f"args: {args}")

            dirsync.sync(
                self.source_directory,
                self.destination_directory,
                "sync",
                **args,
            )

            log_contents = tail.contents()
            self.module.log(msg=f"log_contents: {log_contents}")

            changed, msg = self._evaluate_sync_log(log_contents)

        except Exception as exc:
            failed = True
            msg = f"Directory synchronization failed: {exc}"
        finally:
            logger.removeHandler(handler)
            handler.close()
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate

        return {
            "changed": changed,
            "failed": failed,
            "msg": msg,
        }

    def _validate_directories(self) -> Optional[Dict[str, Any]]:
        """
        Validate the source and destination directory inputs.

        Returns:
            Optional[dict]: Error result dictionary when validation fails,
            otherwise C(None).
        """
        if not os.path.isdir(self.source_directory):
            return {
                "failed": True,
                "changed": False,
                "msg": "The source directory does not exist.",
            }

        if not os.path.isdir(self.destination_directory):
            return {
                "failed": True,
                "changed": False,
                "msg": "The destination directory does not exist.",
            }

        return None

    def _build_filter_pattern(self, patterns: Optional[List[str]]) -> Optional[str]:
        """
        Convert a list of regex fragments into a single dirsync filter regex.

        Args:
            patterns: List of regex fragments.

        Returns:
            Optional[str]: Combined regex string or C(None) when no valid
            patterns were supplied.
        """
        if not patterns:
            return None

        normalized_patterns = [pattern for pattern in patterns if pattern]
        if not normalized_patterns:
            return None

        combined = "|".join(normalized_patterns)
        return f".*(?:{combined}).*"

    def _build_dsync_args(
        self,
        logger: logging.Logger,
        include_pattern: Optional[str],
        exclude_pattern: Optional[str],
    ) -> Dict[str, Any]:
        """
        Build the keyword arguments passed to C(dirsync.sync).

        Args:
            logger: Logger instance used by dirsync.
            include_pattern: Optional include regex.
            exclude_pattern: Optional exclude regex.

        Returns:
            Dict[str, Any]: dirsync keyword argument dictionary.
        """
        if self.arguments and isinstance(self.arguments, dict):
            create = bool(self.arguments.get("create", False))
            verbose = bool(self.arguments.get("verbose", False))
            purge = bool(self.arguments.get("purge", False))
        else:
            create = False
            verbose = False
            purge = False

        args: Dict[str, Any] = {
            "create": create,
            "verbose": verbose,
            "purge": purge,
            "logger": logger,
            "force": True,
        }

        if include_pattern:
            args["include"] = include_pattern

        if exclude_pattern:
            args["exclude"] = exclude_pattern

        return args

    def _evaluate_sync_log(self, log_contents: str) -> Tuple[bool, str]:
        """
        Derive the final change state and status message from dirsync log output.

        Args:
            log_contents: Captured dirsync log output.

        Returns:
            Tuple[bool, str]: Tuple containing the changed flag and the final
            human-readable status message.
        """
        if not log_contents:
            return False, "The directories are already synchronized."

        created_match = re.search(self._DIRECTORIES_CREATED_PATTERN, log_contents)
        if created_match:
            directories = int(created_match.group("directories"))
            if directories > 0:
                return True, "The directories were successfully synchronized."

        copied_match = re.search(self._FILES_COPIED_PATTERN, log_contents)
        if copied_match:
            files_copied = int(copied_match.group("files_copied"))
            if files_copied > 0:
                return True, "The directories were successfully synchronized."

        return False, "The directories are already synchronized."


def main() -> None:
    """
    Create the Ansible module instance and execute the synchronization workflow.

    The function defines the module argument specification, instantiates the
    wrapper class, runs the synchronization logic, and returns the final result
    to Ansible.
    """
    args = dict(
        source_directory=dict(required=True, type="str"),
        destination_directory=dict(required=True, type="str"),
        arguments=dict(required=False, type="dict"),
        include_pattern=dict(required=False, type="list"),
        exclude_pattern=dict(required=False, type="list"),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    module_wrapper = Sync(module)
    result = module_wrapper.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
