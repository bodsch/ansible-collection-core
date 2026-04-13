#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2025-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to return the effective check mode state.

This module provides a minimal compatibility helper for environments where the
magic variable ``ansible_check_mode`` does not reliably expose the effective
runtime state. The module itself does not modify the target system and always
returns a stable result structure.
"""

from __future__ import absolute_import, division, print_function

from typing import Dict

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: check_mode
version_added: "2.5.0"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Return the effective Ansible check mode state.

description:
  - Return whether the current module execution is running in check mode.
  - This module can be used as a lightweight compatibility helper when the
    magic variable C(ansible_check_mode) does not reliably reflect the
    effective execution state.

options: {}

attributes:
  check_mode:
    support: full

notes:
  - This module accepts no parameters.
  - The module never changes the managed host.
"""

EXAMPLES = r"""
- name: Detect effective Ansible check mode
  bodsch.core.check_mode:
  register: _check_mode

- name: Store check mode in a fact
  ansible.builtin.set_fact:
    check_mode: "{{ _check_mode.check_mode }}"

- name: Print current check mode state
  ansible.builtin.debug:
    msg: "check_mode={{ _check_mode.check_mode }}"
"""

RETURN = r"""
check_mode:
  description:
    - Effective check mode state for the current module execution.
  returned: always
  type: bool
  sample: true

changed:
  description:
    - Indicates whether the module changed the managed host.
  returned: always
  type: bool
  sample: false

failed:
  description:
    - Indicates whether the module execution failed.
  returned: always
  type: bool
  sample: false
"""

# ---------------------------------------------------------------------------------------


class CheckMode:
    """
    Minimal helper class for exposing the effective Ansible check mode state.

    The class wraps the active C(AnsibleModule) instance and provides a stable
    public API through C(run()).
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the helper with the active Ansible module instance.

        Args:
            module: Active Ansible module instance.
        """
        self.module = module

    def run(self) -> Dict[str, bool]:
        """
        Build the result payload for the module execution.

        Returns:
            Result dictionary containing the keys C(failed), C(changed), and
            C(check_mode).
        """
        return {
            "failed": False,
            "changed": False,
            "check_mode": bool(self.module.check_mode),
        }


def main() -> None:
    """
    Create the Ansible module, evaluate check mode, and return the result.
    """
    module = AnsibleModule(
        argument_spec={},
        supports_check_mode=True,
    )

    check_mode = CheckMode(module)
    result = check_mode.run()

    # module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
