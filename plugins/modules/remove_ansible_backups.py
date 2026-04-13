#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to remove older Ansible backup files.

This module scans a directory tree for files that match the backup file naming
pattern typically produced by Ansible. Matching files are grouped by their
original file path, sorted chronologically by filename, and older backups are
removed while retaining the configured number of most recent entries.
"""

from __future__ import absolute_import, division, print_function

import os
import re
from typing import Dict, List, Optional, Pattern

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: remove_ansible_backups
version_added: "0.9.0"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Remove older backup files created by Ansible.

description:
  - Search a directory recursively for backup files created by Ansible.
  - Group matching backup files by their original file path.
  - Remove older backups while keeping the configured number of newest files.

options:
  path:
    description:
      - Root directory used to search recursively for backup files.
    type: path
    required: true

  hold:
    description:
      - Number of most recent backup files to retain for each original file.
      - A value of C(0) removes all matching backups.
    type: int
    default: 2
    required: false

  verbose:
    description:
      - Reserved for compatibility with existing playbooks.
      - Currently not used by the module logic.
    type: bool
    required: false

notes:
  - The module supports check mode.
  - Only files matching the expected Ansible backup filename pattern are considered.
"""

EXAMPLES = r"""
- name: Remove older Ansible backup files below /etc and keep four backups
  bodsch.core.remove_ansible_backups:
    path: /etc
    hold: 4

- name: Remove all matching backup files
  bodsch.core.remove_ansible_backups:
    path: /etc
    hold: 0

- name: Preview which backup files would be removed
  bodsch.core.remove_ansible_backups:
    path: /etc
    hold: 2
  check_mode: true
"""

RETURN = r"""
failed:
  description:
    - Indicates whether the module execution failed.
  returned: always
  type: bool
  sample: false

changed:
  description:
    - Indicates whether one or more backup files were removed or would be removed in check mode.
  returned: always
  type: bool
  sample: true

removed:
  description:
    - Removal result payload.
    - Returns a human-readable message when no matching backups were found.
    - Returns a dictionary keyed by original file path when backups were removed.
  returned: always
  type: raw
  sample:
    /etc/example.conf:
      - /etc/example.conf.2024-01-01@12:00:00~
      - /etc/example.conf.2024-01-02@12:00:00~
"""

# ---------------------------------------------------------------------------------------


class RemoveAnsibleBackups(object):
    """
    Remove older Ansible backup files from a directory tree.

    The class encapsulates backup file discovery, grouping, and conditional
    removal logic while keeping the public module API small and stable.
    """

    module = None

    BACKUP_FILE_PATTERN: Pattern[str] = re.compile(
        r"""
        ^
        (?P<file_name>.+?)              # Original file name without the backup suffix
        \.
        .*                              # Optional extension or additional name segment
        \.
        (?P<year>\d{4})-
        (?P<month>\d{2})-
        (?P<day>\d{2})@
        (?P<hour>\d{2}):
        (?P<minute>\d{2}):
        (?P<second>\d{2})
        ~
        $
        """,
        re.VERBOSE,
    )

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the module wrapper and resolve module parameters.

        Args:
            module: Active Ansible module instance providing parameters,
                logging, check mode handling, and result delivery.
        """
        self.module = module

        self.verbose: Optional[bool] = module.params.get("verbose")
        self.path: str = module.params.get("path")
        self.hold: int = module.params.get("hold")

    def run(self) -> Dict[str, object]:
        """
        Execute the module workflow.

        The method searches for matching backup files, removes older entries
        according to the configured retention count, and returns the final
        module result.

        Returns:
            dict: Result dictionary containing C(failed), C(changed), and
            C(removed).
        """
        failed = False
        changed = False
        removed_result: object = "no backups found"

        backups = self.find_backup_files()
        removed = self.remove_backups(backups)

        if len(removed) > 0:
            changed = True
            removed_result = removed

        return dict(failed=failed, changed=changed, removed=removed_result)

    def find_backup_files(self) -> Optional[Dict[str, List[str]]]:
        """
        Search the configured path recursively for Ansible backup files.

        Matching files are grouped by their original file path, which is
        derived from the backup filename.

        Returns:
            Optional[Dict[str, List[str]]]: Dictionary keyed by original file
            path, containing sorted backup file paths. Returns C(None) when the
            configured path does not exist or is not a directory.
        """
        backups: Dict[str, List[str]] = {}

        if not os.path.isdir(self.path):
            return None

        matched_files: List[str] = []

        for root, _dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                if self.BACKUP_FILE_PATTERN.match(filename):
                    matched_files.append(full_path)

        matched_files.sort()

        for backup_file in matched_files:
            file_name = os.path.basename(backup_file)
            path_name = os.path.dirname(backup_file)

            match = self.BACKUP_FILE_PATTERN.search(file_name)
            if not match:
                continue

            original_name = match.group("file_name")
            original_path = os.path.join(path_name, original_name)

            backups.setdefault(original_path, []).append(backup_file)

        return backups

    def remove_backups(
        self,
        backups: Optional[Dict[str, List[str]]],
    ) -> Dict[str, List[str]]:
        """
        Remove old backup files while retaining the configured number of newest entries.

        Args:
            backups: Backup file mapping created by C(find_backup_files()).

        Returns:
            Dict[str, List[str]]: Dictionary keyed by original file path
            containing the list of removed backup files.
        """
        removed_backups: Dict[str, List[str]] = {}

        if not backups:
            return removed_backups

        for original_file, backup_files in backups.items():
            backup_count = len(backup_files)

            self.module.log(
                msg=f"  - file: {original_file} has {backup_count} backup(s)"
            )

            if backup_count <= self.hold:
                continue

            removed_backups[original_file] = []

            if self.hold == 0:
                backups_to_remove = backup_files
            else:
                backups_to_remove = backup_files[: -self.hold]

            for backup_file in backups_to_remove:
                if not os.path.isfile(backup_file):
                    continue

                if self.module.check_mode:
                    self.module.log(msg=f"CHECK MODE - remove {backup_file}")
                else:
                    self.module.log(msg=f"  - remove {backup_file}")
                    os.remove(backup_file)

                removed_backups[original_file].append(backup_file)

        return removed_backups


def main() -> None:
    """
    Create the Ansible module instance and execute the backup cleanup workflow.

    The function defines the module argument specification, initializes the
    wrapper class, executes the module logic, and returns the final result to
    Ansible.
    """
    args = dict(
        verbose=dict(
            type="bool",
            required=False,
        ),
        path=dict(
            type="path",
            required=True,
        ),
        hold=dict(
            type="int",
            required=False,
            default=2,
        ),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    module_wrapper = RemoveAnsibleBackups(module)
    result = module_wrapper.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
