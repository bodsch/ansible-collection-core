#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2022, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, print_function

import re

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: syslog_cmd
version_added: "1.1.3"
short_description: Run syslog-ng with arbitrary command-line parameters
author:
  - "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

description:
  - Executes the C(syslog-ng) binary with the given list of parameters.
  - Typical use cases are configuration syntax validation and querying the installed version.

requirements:
  - syslog-ng

options:
  parameters:
    description:
      - List of command-line parameters to pass to C(syslog-ng).
      - Each list item may contain a single parameter or a parameter with a value.
      - Items containing spaces are split into multiple arguments before execution.
    type: list
    elements: str
    required: true

notes:
  - The module supports check mode.
  - When used with C(--version) or C(--syntax-only) in check mode, no external command is executed and simulated results are returned.
"""

EXAMPLES = r"""
- name: Validate syslog-ng configuration
  bodsch.core.syslog_cmd:
    parameters:
      - --syntax-only
  check_mode: true
  when:
    - not ansible_check_mode

- name: Detect syslog-ng config version
  bodsch.core.syslog_cmd:
    parameters:
      - --version
  register: _syslog_config_version

- name: Run syslog-ng with custom parameters
  bodsch.core.syslog_cmd:
    parameters:
      - --control
      - show-config
  register: _syslog_custom_cmd
"""

RETURN = r"""
rc:
  description:
    - Return code from the C(syslog-ng) command.
  returned: always
  type: int

failed:
  description:
    - Indicates if the module execution failed.
  returned: always
  type: bool

args:
  description:
    - Full command list used to invoke C(syslog-ng).
    - Will be C(None) when running in check mode.
  returned: when a supported command is executed or simulated
  type: list

version:
  description:
    - Detected C(syslog-ng) version string (for example C(3.38)).
  returned: when C(--version) is present in I(parameters)
  type: str

msg:
  description:
    - Human readable message, for example C("syntax okay") for successful syntax checks or an error description.
  returned: when available
  type: str

stdout:
  description:
    - Standard output from the C(syslog-ng) command.
    - In check mode with C(--syntax-only), contains a simulated message.
  returned: when C(--syntax-only) is used or on error
  type: str

stderr:
  description:
    - Standard error from the C(syslog-ng) command.
  returned: when C(--syntax-only) is used and the command fails
  type: str

ansible_module_results:
  description:
    - Internal result marker, set to C("failed") when no supported action was executed.
  returned: when no supported parameters were processed
  type: str
"""


# ---------------------------------------------------------------------------------------


class SyslogNgCmd(object):
    module = None

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module

        self._syslog_ng_bin = module.get_bin_path("syslog-ng", False)
        self.parameters = module.params.get("parameters")

    def run(self):
        """..."""
        result = dict(failed=True, ansible_module_results="failed")

        parameter_list = self._flatten_parameter()

        self.module.debug("-> {parameter_list}")

        if self.module.check_mode:
            self.module.debug("In check mode.")
            if "--version" in parameter_list:
                return dict(rc=0, failed=False, args=None, version="1")
            if "--syntax-only" in parameter_list:
                return dict(
                    rc=0,
                    failed=False,
                    args=None,
                    stdout="In check mode.",
                    stderr="",
                )

        if not self._syslog_ng_bin:
            return dict(rc=1, failed=True, msg="no installed syslog-ng found")

        args = []
        args.append(self._syslog_ng_bin)

        if len(parameter_list) > 0:
            for arg in parameter_list:
                args.append(arg)

        self.module.log(msg=f" - args {args}")

        rc, out, err = self._exec(args)

        if "--version" in parameter_list:
            """
            get version"
            """
            pattern = re.compile(
                r".*Installer-Version: (?P<version>\d\.\d+)\.", re.MULTILINE
            )
            version = re.search(pattern, out)
            version = version.group(1)

            self.module.log(msg=f"   version: '{version}'")

            if rc == 0:
                return dict(rc=0, failed=False, args=args, version=version)

        if "--syntax-only" in parameter_list:
            """
            check syntax
            """
            # self.module.log(msg=f"   rc : '{rc}'")
            # self.module.log(msg=f"   out: '{out}'")
            # self.module.log(msg=f"   err: '{err}'")

            if rc == 0:
                return dict(rc=rc, failed=False, args=args, msg="syntax okay")
            else:
                return dict(
                    rc=rc,
                    failed=True,
                    args=args,
                    stdout=out,
                    stderr=err,
                )

        return result

    def _exec(self, args):
        """ """
        rc, out, err = self.module.run_command(args, check_rc=True)
        # self.module.log(msg="  rc : '{}'".format(rc))
        # self.module.log(msg="  out: '{}' ({})".format(out, type(out)))
        # self.module.log(msg="  err: '{}'".format(err))
        return rc, out, err

    def _flatten_parameter(self):
        """
        split and flatten parameter list

        input:  ['--validate', '--log-level debug']
        output: ['--validate', '--log-level', 'debug']
        """
        parameters = []

        for _parameter in self.parameters:
            if " " in _parameter:
                _list = _parameter.split(" ")
                for _element in _list:
                    parameters.append(_element)
            else:
                parameters.append(_parameter)

        return parameters


# ===========================================
# Module execution.
#


def main():

    module = AnsibleModule(
        argument_spec=dict(
            parameters=dict(required=True, type="list"),
        ),
        supports_check_mode=True,
    )

    c = SyslogNgCmd(module)
    result = c.run()

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
