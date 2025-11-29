#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import os
import re

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: remove_ansible_backups
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Remove older backup files created by ansible

description:
    - Remove older backup files created by ansible

options:
  path:
    description:
      - Path for the search for backup files
    type: str
    required: true
  hold:
    description:
      - How many backup files should be retained
    type: int
    default: 2
    required: false
"""

EXAMPLES = """
- name: remove older ansible backup files
  bodsch.core.remove_ansible_backups:
    path: /etc
    holds: 4
"""

RETURN = """
removed:
    returned: on success
    description: >
        Job's up to date information
    type: dict
"""

# ---------------------------------------------------------------------------------------


class RemoveAnsibleBackups(object):
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module

        self.verbose = module.params.get("verbose")
        self.path = module.params.get("path")
        self.hold = module.params.get("hold")

    def run(self):
        """
        runner
        """
        _failed = False
        _changed = False
        _msg = "no backups found"

        backups = self.find_backup_files()
        removed = self.remove_backups(backups)

        if len(removed) > 0:
            _changed = True
            _msg = removed

        return dict(failed=_failed, changed=_changed, removed=_msg)

    def find_backup_files(self):
        """ """
        _files = []
        _name = None
        backup_files = []
        backups = dict()

        if os.path.isdir(self.path):
            """ """
            os.chdir(self.path)

            # file_pattern = re.compile(r"
            #   (?P<file_name>.*)\.(.*)\.(?P<year>\d{4})-(?P<month>.{2})-
            #   (?P<day>\d+)@(?P<hour>\d+):(?P<minute>\d+):(?P<second>\d{2})~", re.MULTILINE)

            file_pattern = re.compile(
                r"""
                (?P<file_name>.*)\.           # Alles vor dem ersten Punkt (Dateiname)
                (.*)\.                        # Irgendein Teil nach dem ersten Punkt (z.B. Erweiterung)
                (?P<year>\d{4})-              # Jahr (4-stellig)
                (?P<month>.{2})-             # Monat (2 Zeichen – ggf. besser \d{2}?)
                (?P<day>\d+)@                # Tag, dann @
                (?P<hour>\d+):               # Stunde
                (?P<minute>\d+):             # Minute
                (?P<second>\d{2})~           # Sekunde, dann Tilde
                """,
                re.VERBOSE | re.MULTILINE,
            )

            # self.module.log(msg=f"search files in {self.path}")

            # recursive file list
            for root, dirnames, filenames in os.walk(self.path):
                for filename in filenames:
                    _files.append(os.path.join(root, filename))

            # filter file list wirth regex
            backup_files = list(filter(file_pattern.match, _files))
            backup_files.sort()

            for f in backup_files:
                """ """
                file_name = os.path.basename(f)
                path_name = os.path.dirname(f)

                name = re.search(file_pattern, file_name)

                if name:
                    n = name.group("file_name")
                    _idx = os.path.join(path_name, n)

                    if str(n) == str(_name):
                        backups[_idx].append(f)
                    else:
                        backups[_idx] = []
                        backups[_idx].append(f)

                    _name = n

            return backups

        else:
            return None

    def remove_backups(self, backups):
        """ """
        _backups = dict()

        for k, v in backups.items():
            backup_count = len(v)

            self.module.log(msg=f"  - file: {k} has  {backup_count} backup(s)")

            if backup_count > self.hold:
                """ """
                _backups[k] = []

                # bck_hold = v[self.hold:]
                bck_to_remove = v[: -self.hold]
                # self.module.log(msg=f"  - hold backups: {bck_hold}")
                # self.module.log(msg=f"  - remove backups: {bck_to_remove}")

                for bck in bck_to_remove:
                    if os.path.isfile(bck):
                        if self.module.check_mode:
                            self.module.log(msg=f"CHECK MODE - remove {bck}")
                        else:
                            self.module.log(msg=f"  - remove {bck}")

                        if not self.module.check_mode:
                            os.remove(bck)

                        _backups[k].append(bck)

        return _backups


# ===========================================
# Module execution.
#


def main():

    args = dict(
        verbose=dict(
            type="bool",
            required=False,
        ),
        path=dict(
            type="path",
            required=True,
        ),
        hold=dict(type="int", required=False, default=2),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    postfix = RemoveAnsibleBackups(module)
    result = postfix.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
