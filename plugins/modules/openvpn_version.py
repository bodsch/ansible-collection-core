#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to read and parse the installed OpenVPN version.

This module executes ``openvpn --version`` on the target host, extracts the
semantic version string from the command output, and returns both the parsed
version and the raw stdout for troubleshooting purposes.
"""

from __future__ import absolute_import, division, print_function

import re

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: openvpn_version
short_description: Read the installed OpenVPN version
version_added: "1.1.3"
author:
  - Bodo Schulz (@bodsch) <me+ansible@bodsch.me>

description:
  - Executes C(openvpn --version) on the target host.
  - Parses the semantic version (C(X.Y.Z)) from the output.
  - Returns the full stdout and stdout_lines for troubleshooting.

options: {}

notes:
  - Check mode is not supported.
  - The module fails if the C(openvpn) binary cannot be found on the target host.

requirements:
  - OpenVPN installed on the target host.
"""

EXAMPLES = r"""
- name: Get OpenVPN version
  bodsch.core.openvpn_version:
  register: openvpn

- name: Print parsed version
  ansible.builtin.debug:
    msg: "OpenVPN version: {{ openvpn.version }}"

- name: Print raw stdout for troubleshooting
  ansible.builtin.debug:
    var: openvpn.stdout_lines
"""

RETURN = r"""
version:
  description:
    - Parsed OpenVPN version (C(X.Y.Z)) if found, otherwise C(unknown).
  returned: always
  type: str
  sample: "2.6.8"

stdout:
  description:
    - Raw stdout from C(openvpn --version).
  returned: always
  type: str

stdout_lines:
  description:
    - Stdout split into lines.
  returned: always
  type: list
  elements: str

failed:
  description:
    - Indicates whether parsing the version failed.
  returned: always
  type: bool
"""

# ---------------------------------------------------------------------------------------


class OpenVPN(object):
    """
    Query and parse the installed OpenVPN version.

    The class encapsulates binary discovery, command execution, and extraction
    of the semantic version string from the OpenVPN version output.
    """

    module = None

    def __init__(self, module):
        """
        Initialize the module wrapper and resolve the OpenVPN binary path.

        Args:
            module: Active Ansible module instance used for parameter access,
                logging, and command execution.
        """
        self.module = module

        self._openvpn = module.get_bin_path("openvpn", True)

    def run(self):
        """
        Execute the version lookup workflow.

        The method runs ``openvpn --version``, searches the command output for a
        semantic version string, and returns the parsed version together with
        the raw stdout content.

        Returns:
            dict: Result dictionary containing C(stdout), C(stdout_lines),
            C(failed), and C(version).
        """
        _failed = True
        _version = "unknown"
        _stdout = ""
        _stdout_lines = []

        args = []

        args.append(self._openvpn)
        args.append("--version")

        rc, out = self._exec(args)

        if "OpenVPN" in out:
            pattern = re.compile(
                r"OpenVPN (?P<version>[0-9]+\.[0-9]+\.[0-9]+).*", re.MULTILINE
            )
            found = re.search(pattern, out.rstrip())

            if found:
                _version = found.group("version")
                _failed = False
        else:
            _failed = True

        _stdout = f"{out.rstrip()}"
        _stdout_lines = _stdout.split("\n")

        return dict(
            stdout=_stdout, stdout_lines=_stdout_lines, failed=_failed, version=_version
        )

    def _exec(self, commands):
        """
        Execute a command through the Ansible module helper.

        If the command exits with a non-zero return code, stdout and stderr are
        written to the module log for troubleshooting.

        Args:
            commands: Command argument list passed to C(run_command).

        Returns:
            tuple: Two-element tuple containing the return code and stdout.
        """
        rc, out, err = self.module.run_command(commands, check_rc=False)

        if int(rc) != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out


def main():
    """
    Create the Ansible module instance and execute the version lookup.

    The function defines the argument specification, instantiates the module
    wrapper class, executes the workflow, and returns the final result to
    Ansible.
    """
    args = dict()

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    o = OpenVPN(module)
    result = o.run()

    module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
