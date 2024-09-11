#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2022, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, print_function

import re

from ansible.module_utils.basic import AnsibleModule


class SyslogNgCmd(object):
    module = None

    def __init__(self, module):
        """
          Initialize all needed Variables
        """
        self.module = module

        self._syslog_ng_bin = module.get_bin_path('syslog-ng', True)
        self.parameters = module.params.get("parameters")

    def run(self):
        ''' ... '''
        result = dict(
            failed=True,
            ansible_module_results='failed'
        )

        parameter_list = self._flatten_parameter()

        if not self._syslog_ng_bin:
            return dict(
                rc=1,
                failed=True,
                msg="no installed syslog-ng found"
            )

        args = []
        args.append(self._syslog_ng_bin)

        if len(parameter_list) > 0:
            for arg in parameter_list:
                args.append(arg)

        self.module.log(msg=f" - args {args}")

        rc, out, err = self._exec(args)

        if '--version' in parameter_list:
            """
              get version"
            """
            pattern = re.compile(r'.*Installer-Version: (?P<version>\d\.\d+)\.', re.MULTILINE)
            version = re.search(pattern, out)
            version = version.group(1)

            self.module.log(msg=f"   version: '{version}'")

            if (rc == 0):
                return dict(
                    rc=0,
                    failed=False,
                    args=args,
                    version=version
                )

        if '--syntax-only' in parameter_list:
            """
              check syntax
            """
            self.module.log(msg=f"   rc : '{rc}'")
            self.module.log(msg=f"   out: '{out}'")
            self.module.log(msg=f"   err: '{err}'")

            if rc == 0:
                return dict(
                    rc=rc,
                    failed=False,
                    args=args,
                    msg="syntax okay"
                )
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
        """
        """
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
            if ' ' in _parameter:
                _list = _parameter.split(' ')
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
            parameters=dict(required=True, type='list'),
        ),
        supports_check_mode=True,
    )

    c = SyslogNgCmd(module)
    result = c.run()

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
