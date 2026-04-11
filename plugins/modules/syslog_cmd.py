#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to execute syslog-ng with selected command-line parameters.

This module wraps the ``syslog-ng`` binary and supports a small set of common
operational tasks such as syntax validation and version detection. It keeps the
public API compact while providing consistent return structures for supported
commands.
"""

from __future__ import absolute_import, print_function

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: syslog_cmd
version_added: "1.1.3"
short_description: Run syslog-ng with arbitrary command-line parameters.
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

description:
  - Execute the C(syslog-ng) binary with the given list of parameters.
  - Common use cases are configuration syntax validation and querying the
    installed version.

requirements:
  - syslog-ng

options:
  parameters:
    description:
      - List of command-line parameters passed to C(syslog-ng).
      - Each item may contain a single parameter or a parameter together with
        its value.
      - Items containing whitespace are split into multiple arguments before
        execution.
    type: list
    elements: str
    required: true

notes:
  - The module supports check mode.
  - In check mode, supported operations are simulated and no external command
    is executed.
"""

EXAMPLES = r"""
- name: Validate syslog-ng configuration
  bodsch.core.syslog_cmd:
    parameters:
      - --syntax-only
  register: _syslog_syntax

- name: Detect syslog-ng version
  bodsch.core.syslog_cmd:
    parameters:
      - --version
  register: _syslog_version

- name: Run syslog-ng with custom parameters
  bodsch.core.syslog_cmd:
    parameters:
      - --control
      - show-config
  register: _syslog_custom_cmd

- name: Simulate syntax check in check mode
  bodsch.core.syslog_cmd:
    parameters:
      - --syntax-only
  check_mode: true
"""

RETURN = r"""
rc:
  description:
    - Return code from the C(syslog-ng) command or the simulated result.
  returned: when a supported action was executed or simulated
  type: int
  sample: 0

failed:
  description:
    - Indicates whether the module execution failed.
  returned: always
  type: bool
  sample: false

args:
  description:
    - Full command list used to invoke C(syslog-ng).
    - Will be C(None) in check mode.
  returned: when a supported action was executed or simulated
  type: list
  elements: str

version:
  description:
    - Detected C(syslog-ng) version string.
  returned: when C(--version) is present in I(parameters)
  type: str
  sample: "4.8.1"

msg:
  description:
    - Human-readable status or error message.
  returned: when available
  type: str
  sample: "syntax okay"

stdout:
  description:
    - Standard output from the C(syslog-ng) command.
  returned: when available
  type: str

stderr:
  description:
    - Standard error from the C(syslog-ng) command.
  returned: when available
  type: str

ansible_module_results:
  description:
    - Internal fallback result marker used when no supported action was processed.
  returned: when no supported parameters were processed
  type: str
  sample: "failed"
"""

# ---------------------------------------------------------------------------------------


class SyslogNgCmd(object):
    """
    Execute selected syslog-ng commands and normalize their results.

    The class resolves the syslog-ng binary, normalizes the configured
    parameter list, executes supported commands, and returns structured module
    results for version queries and syntax validation.
    """

    module = None

    _VERSION_PATTERNS: Tuple[re.Pattern[str], ...] = (
        re.compile(r".*Installer-Version: (?P<version>\d+\.\d+)\.", re.MULTILINE),
        re.compile(r"syslog-ng\s+(?P<version>\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
    )

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the module wrapper and resolve runtime parameters.

        Args:
            module: Active Ansible module instance used for parameter access,
                logging, command execution, and result handling.
        """
        self.module = module

        self._syslog_ng_bin: Optional[str] = module.get_bin_path("syslog-ng", False)
        self.parameters: List[str] = module.params.get("parameters") or []

    def run(self) -> Dict[str, Any]:
        """
        Execute the requested syslog-ng command workflow.

        The method supports two primary operations:
        version detection via C(--version) and syntax validation via
        C(--syntax-only). Unsupported parameter combinations fall back to the
        legacy failure result.

        Returns:
            dict: Normalized Ansible module result.
        """
        result: Dict[str, Any] = {
            "failed": True,
            "ansible_module_results": "failed",
        }

        parameter_list = self._flatten_parameter()

        self.module.debug(f"-> {parameter_list}")

        if len(parameter_list) == 0:
            return {
                "rc": 1,
                "failed": True,
                "msg": "no parameters provided",
            }

        if self.module.check_mode:
            self.module.debug("In check mode.")

            if "--version" in parameter_list:
                return {
                    "rc": 0,
                    "failed": False,
                    "args": None,
                    "version": "unknown",
                    "msg": "version detection skipped in check mode",
                }

            if "--syntax-only" in parameter_list:
                return {
                    "rc": 0,
                    "failed": False,
                    "args": None,
                    "msg": "syntax okay",
                    "stdout": "In check mode.",
                    "stderr": "",
                }

        if not self._syslog_ng_bin:
            return {
                "rc": 1,
                "failed": True,
                "msg": "no installed syslog-ng found",
            }

        args: List[str] = [self._syslog_ng_bin]
        args.extend(parameter_list)

        # self.module.log(msg=f" - args {args}")

        rc, out, err = self._exec(args)

        if "--version" in parameter_list:
            version = self._extract_version(out)

            if rc == 0 and version is not None:
                return {
                    "rc": 0,
                    "failed": False,
                    "args": args,
                    "version": version,
                }

            return {
                "rc": rc,
                "failed": True,
                "args": args,
                "stdout": out,
                "stderr": err,
                "msg": "unable to detect syslog-ng version",
                "version": "unknown",
            }

        if "--syntax-only" in parameter_list:
            if rc == 0:
                return {
                    "rc": rc,
                    "failed": False,
                    "args": args,
                    "msg": "syntax okay",
                    "stdout": out,
                    "stderr": err,
                }

            return {
                "rc": rc,
                "failed": True,
                "args": args,
                "stdout": out,
                "stderr": err,
            }

        return result

    def _exec(self, args: Sequence[str]) -> Tuple[int, str, str]:
        """
        Execute a syslog-ng command through the Ansible module helper.

        The command is executed with C(check_rc=False) so the caller can decide
        how to interpret non-zero return codes.

        Args:
            args: Full command argument list.

        Returns:
            tuple: Tuple containing return code, stdout, and stderr.
        """
        rc, out, err = self.module.run_command(list(args), check_rc=False)

        if int(rc) != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err

    def _flatten_parameter(self) -> List[str]:
        """
        Split and flatten the configured parameter list.

        Each list item may contain one or more whitespace-separated arguments.
        Empty fragments are ignored.

        Example:
            Input: C(['--validate', '--log-level debug'])
            Output: C(['--validate', '--log-level', 'debug'])

        Returns:
            list: Flattened argument list.
        """
        flattened: List[str] = []

        for parameter in self.parameters:
            if " " in parameter:
                flattened.extend([element for element in parameter.split() if element])
            else:
                flattened.append(parameter)

        return flattened

    def _extract_version(self, output: str) -> Optional[str]:
        """
        Extract the syslog-ng version string from command output.

        The method supports multiple output formats to be more robust across
        syslog-ng builds and distributions.

        Args:
            output: Standard output of C(syslog-ng --version).

        Returns:
            Optional[str]: Parsed version string or C(None) if no version could
            be detected.
        """
        normalized_output = output.rstrip()

        for pattern in self._VERSION_PATTERNS:
            match = pattern.search(normalized_output)
            if match:
                version = match.group("version")
                # self.module.log(msg=f"   version: '{version}'")
                return version

        return None


def main() -> None:
    """
    Create the Ansible module instance and execute the command workflow.

    The function defines the argument specification, initializes the module
    wrapper, executes the requested action, and returns the final result to
    Ansible.
    """
    module = AnsibleModule(
        argument_spec=dict(
            parameters=dict(required=True, type="list"),
        ),
        supports_check_mode=True,
    )

    module_wrapper = SyslogNgCmd(module)
    result = module_wrapper.run()

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
