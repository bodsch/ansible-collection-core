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

short_description: another solution for ansible_check_mode

description:
    - returns a valid state for check_mode

options:
"""

# ---------------------------------------------------------------------------------------

class CheckMode(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self._openvpn = module.get_bin_path('/bin/true', True)

    def run(self):
        """
        """
        if self.module.check_mode:
            return dict(
                failed=False,
                changed=False,
                check_mode=True
            )
        else:
            return dict(
                failed=False,
                changed=False,
                check_mode=False
            )

    def _exec(self, commands):
        """
        """
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
        supports_check_mode=True,
    )

    o = CheckMode(module)
    result = o.run()

    module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
