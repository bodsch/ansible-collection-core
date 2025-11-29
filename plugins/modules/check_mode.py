#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: check_mode
version_added: 2.5.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Replacement for ansible_check_mode.

description:
    - Replacement for ansible_check_mode.
    - The magic variable `ansible_check_mode` was not defined with the correct value in some cases.

options:
"""

EXAMPLES = r"""
- name: detect ansible check_mode
  bodsch.core.check_mode:
  register: _check_mode

- name: define check_mode
  ansible.builtin.set_fact:
    check_mode: '{{ _check_mode.check_mode }}'
"""

RETURN = r"""
check_mode:
  description:
    - Status for check_mode.
  type: bool
"""

# ---------------------------------------------------------------------------------------


class CheckMode(object):
    """ """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

    def run(self):
        """ """
        result = dict(failed=False, changed=False, check_mode=False)

        if self.module.check_mode:
            result = dict(failed=False, changed=False, check_mode=True)

        return result


def main():

    args = dict()

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    o = CheckMode(module)
    result = o.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
