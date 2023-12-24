#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2021-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0/)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function
import os
import re

from ansible.module_utils.basic import AnsibleModule


__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class SnakeoilOpenssl(object):
    """
      Main Class
    """
    module = None

    def __init__(self, module):
        """
          Initialize all needed Variables
        """
        self.module = module

        self._openssl = module.get_bin_path('openssl', True)
        self.state = module.params.get("state")
        self.directory = module.params.get("directory")
        self.domain = module.params.get("domain")
        self.dhparam = module.params.get("dhparam")
        self.cert_life_time = module.params.get("cert_life_time")
        self.openssl_config = module.params.get("openssl_config")

    def run(self):
        """
        """
        result = dict(
            failed=True,
            changed=False,
            msg="failed"
        )

        base_directory = os.path.join(self.directory, self.domain)

        if not os.path.isdir(base_directory):
            return dict(
                failed=True,
                changed=False,
                msg=f"missing directory {base_directory}"
            )

        os.chdir(base_directory)
        _ssl_args = []

        csr_file = os.path.join(self.directory, self.domain, f"{self.domain}.csr")
        crt_file = os.path.join(self.directory, self.domain, f"{self.domain}.crt")
        pem_file = os.path.join(self.directory, self.domain, f"{self.domain}.pem")
        key_file = os.path.join(self.directory, self.domain, f"{self.domain}.key")
        dh_file = os.path.join(self.directory, self.domain, "dh.pem")

        if self.state == "csr":
            _ssl_args.append(self._openssl)
            _ssl_args.append("req")
            _ssl_args.append("-new")
            _ssl_args.append("-sha512")
            _ssl_args.append("-nodes")
            _ssl_args.append("-out")
            _ssl_args.append(csr_file)
            _ssl_args.append("-newkey")
            _ssl_args.append("rsa:4096")
            _ssl_args.append("-keyout")
            _ssl_args.append(key_file)
            _ssl_args.append("-config")
            _ssl_args.append(self.openssl_config)

            rc, out, err = self._exec(_ssl_args)

            result = dict(
                failed=False,
                changed=True,
                msg="success"
            )

        if self.state == "crt":
            _ssl_args.append(self._openssl)
            _ssl_args.append("x509")
            _ssl_args.append("-req")
            _ssl_args.append("-in")
            _ssl_args.append(csr_file)
            _ssl_args.append("-out")
            _ssl_args.append(crt_file)
            _ssl_args.append("-signkey")
            _ssl_args.append(key_file)
            _ssl_args.append("-extfile")
            _ssl_args.append(self.openssl_config)
            _ssl_args.append("-extensions")
            _ssl_args.append("req_ext")
            _ssl_args.append("-days")
            _ssl_args.append(str(self.cert_life_time))

            rc, out, err = self._exec(_ssl_args)

            # cat {{ domain }}.crt {{ domain }}.key >> {{ domain }}.pem
            if rc == 0:
                filenames = [crt_file, key_file]
                with open(pem_file, 'w') as outfile:
                    for fname in filenames:
                        with open(fname) as infile:
                            outfile.write(infile.read())

            result = dict(
                failed=False,
                changed=True,
                msg="success"
            )

        if self.state == "dhparam":
            _ssl_args.append(self._openssl)
            _ssl_args.append("dhparam")
            _ssl_args.append("-5")
            _ssl_args.append("-out")
            _ssl_args.append(dh_file)
            _ssl_args.append(str(self.dhparam))

            rc, out, err = self._exec(_ssl_args)

            result = dict(
                failed=False,
                changed=True,
                msg="success"
            )

        if self.state == "dhparam_size":
            _ssl_args.append(self._openssl)
            _ssl_args.append("dhparam")
            _ssl_args.append("-in")
            _ssl_args.append(dh_file)
            _ssl_args.append("-text")

            rc, out, err = self._exec(_ssl_args)

            if rc == 0:
                """
                """
                output_string = 0
                pattern = re.compile(r".*DH Parameters: \((?P<size>\d+) bit\).*")

                result = re.search(pattern, out)
                if result:
                    output_string = result.group('size')

            result = dict(
                failed=False,
                changed=False,
                size=int(output_string)
            )

        return result

    def _exec(self, args):
        """
        """
        self.module.log(msg="args: {}".format(args))

        rc, out, err = self.module.run_command(args, check_rc=True)
        self.module.log(msg="  rc : '{}'".format(rc))
        if rc != 0:
            self.module.log(msg="  out: '{}'".format(str(out)))
            self.module.log(msg="  err: '{}'".format(err))

        return rc, out, err


# ===========================================
# Module execution.
#


def main():
    """
    """
    args = dict(
        state=dict(
            required=True,
            choose=[
                'crt',
                'csr',
                'dhparam'
                'dhparam_size'
            ]
        ),
        directory=dict(
            required=True,
            type="path"
        ),
        domain=dict(
            required=True,
            type="path"
        ),
        dhparam=dict(
            default=2048,
            type="int"
        ),
        cert_life_time=dict(
            default=10,
            type="int"
        ),
        openssl_config=dict(
            required=False,
            type="str"
        ),
        # openssl_params=dict(required=True, type="path"),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    openssl = SnakeoilOpenssl(module)
    result = openssl.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
