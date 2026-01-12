#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

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
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

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
    """ """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        self._openvpn = module.get_bin_path("openvpn", True)

    def run(self):
        """
        runner
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
        """ """
        rc, out, err = self.module.run_command(commands, check_rc=False)

        if int(rc) != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out


# ===========================================
# Module execution.
#


def main():

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
