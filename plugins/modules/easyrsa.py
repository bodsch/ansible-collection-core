#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import os
import shutil

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: easyrsa
version_added: 1.1.3
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Accepts CLI commandos for syslog-ng.

description:
    - Accepts CLI commandos for syslog-ng.

options:
  source_directory:
    parameters:
      - A list of parameters.
    type: list
    default: []
    required: true
"""

EXAMPLES = r"""
- name: validate syslog-ng config
  bodsch.core.syslog_cmd:
    parameters:
      - --syntax-only
  check_mode: true
  when:
    - not ansible_check_mode

- name: detect config version
  bodsch.core.syslog_cmd:
    parameters:
      - --version
  register: _syslog_config_version
"""

RETURN = r"""
failed:
  description:
    - changed or not
  type: int
failed:
  description:
    - Failed, or not.
  type: bool
args:
  description:
    - Arguments with which syslog-ng is called.
  type: str

"""

# ---------------------------------------------------------------------------------------


class EasyRsa(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.state = ""

        self.force = module.params.get("force", False)
        self.pki_dir = module.params.get('pki_dir', None)
        self.req_cn_ca = module.params.get('req_cn_ca', None)
        self.req_cn_server = module.params.get('req_cn_server', None)
        self.ca_keysize = module.params.get('ca_keysize', None)
        self.dh_keysize = module.params.get('dh_keysize', None)
        self.working_dir = module.params.get('working_dir', None)

        self.easyrsa = module.get_bin_path('easyrsa', True)

    def run(self):
        """
          runner
        """
        result_state = []

        if self.working_dir:
            os.chdir(self.working_dir)

        self.module.log(msg=f"-> pwd : {os.getcwd()}")

        if self.force:
            self.module.log(msg="force mode ...")
            self.module.log(msg=f"remove {self.pki_dir}")

            if os.path.isdir(self.pki_dir):
                shutil.rmtree(self.pki_dir)

        for p in ["init-pki", "build-ca", "gen-crl", "gen-req", "sign-req", "gen-dh"]:
            req = {}
            self.module.log(msg=f"  - {p}")

            if p == "init-pki":
                rc, changed, msg = self.create_pki()
            if p == "build-ca" and rc == 0:
                rc, changed, msg = self.build_ca()
            if p == "gen-crl" and rc == 0:
                rc, changed, msg = self.gen_crl()
            if p == "gen-req" and rc == 0:
                rc, changed, msg = self.gen_req()
            if p == "sign-req" and rc == 0:
                rc, changed, msg = self.sign_req()
            if p == "gen-dh" and rc == 0:
                rc, changed, msg = self.gen_dh()

            req[p] = dict(
                failed=not (rc == 0),
                changed=changed,
                msg=msg
            )

            result_state.append(req)

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=failed,
            state=result_state
        )

        return result

    # ----------------------------------------------------------------------------------------------
    # PRIVATE API - create
    def create_pki(self):
        """
        """
        self.module.log(msg="EasyRsa::create_pki()")

        if self.validate_pki():
            return (0, False, "PKI already created")

        args = []
        args.append(self.easyrsa)
        args.append("init-pki")

        rc, out, err = self._exec(args)

        if self.validate_pki():
            return (0, True, "The PKI was successfully created.")
        else:
            return (1, True, "An error occurred while creating the PKI.")

    def build_ca(self):
        """
        """
        if self.validate_ca():
            return (0, False, "CA already created")

        args = []
        args.append(self.easyrsa)
        args.append("--batch")
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append(f"--req-cn={self.req_cn_ca}")

        if self.ca_keysize:
            args.append(f"--keysize={self.ca_keysize}")
        args.append("build-ca")
        args.append("nopass")

        rc, out, err = self._exec(args)

        _out = out.splitlines()
        _err = err.splitlines()
        # self.module.log(msg=f"= _out: {_out} {type(_out)}")
        # self.module.log(msg=f"= _err: {_err} {type(_err)}")
        _output = []
        _output += _out
        _output += _err
        self.module.log(msg=f"= output: {_output}")

        ca_crt_file = "/usr/share/easy-rsa/pki/ca.crt"
        ca_key_file = "/usr/share/easy-rsa/pki/private/ca.key"

        if os.path.exists(ca_crt_file) and os.path.exists(ca_key_file):
            rc = 0
            _output = "ca.crt and ca.key were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def gen_crl(self):
        """
        """
        if self.validate_crl():
            return (0, False, "CRL already created")

        args = []
        args.append(self.easyrsa)
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append("gen-crl")

        rc, out, err = self._exec(args)

        _out = out.splitlines()
        _err = err.splitlines()
        # self.module.log(msg=f"= _out: {_out} {type(_out)}")
        # self.module.log(msg=f"= _err: {_err} {type(_err)}")
        _output = []
        _output += _out
        _output += _err
        self.module.log(msg=f"= output: {_output}")

        crl_pem_file = "/usr/share/easy-rsa/pki/crl.pem"

        if os.path.exists(crl_pem_file):
            rc = 0
            _output = "crl.pem were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def gen_req(self):
        """
        """
        if self.validate_req():
            return (0, False, "keypair and request already created")

        args = []
        args.append(self.easyrsa)
        args.append("--batch")
        # args.append(f"--pki-dir={self._pki_dir}")
        if self.req_cn_ca:
            args.append(f"--req-cn={self.req_cn_ca}")
        args.append("gen-req")
        args.append(self.req_cn_server)
        args.append("nopass")

        rc, out, err = self._exec(args)

        _out = out.splitlines()
        _err = err.splitlines()
        # self.module.log(msg=f"= _out: {_out} {type(_out)}")
        # self.module.log(msg=f"= _err: {_err} {type(_err)}")
        _output = []
        _output += _out
        _output += _err
        self.module.log(msg=f"= output: {_output}")

        req_file = f"/usr/share/easy-rsa/pki/reqs/{self.req_cn_server}.req"

        if os.path.exists(req_file):
            rc = 0
            _output = f"{self.req_cn_server}.req were successfully created."
        else:
            rc = 3

        return (rc, True , _output)

    def sign_req(self):
        """
        """
        if self.validate_sign():
            return (0, False, "certificate alread signed")

        args = []
        args.append(self.easyrsa)
        args.append("--batch")
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append("sign-req")
        args.append("server")
        args.append(self.req_cn_server)

        rc, out, err = self._exec(args)

        _out = out.splitlines()
        _err = err.splitlines()
        # self.module.log(msg=f"= _out: {_out} {type(_out)}")
        # self.module.log(msg=f"= _err: {_err} {type(_err)}")
        _output = []
        _output += _out
        _output += _err
        self.module.log(msg=f"= output: {_output}")

        crt_file = f"/usr/share/easy-rsa/pki/issued/{self.req_cn_server}.crt"

        if os.path.exists(crt_file):
            rc = 0
            _output = f"{self.req_cn_server}.crt were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def gen_dh(self):
        """
        """
        if self.validate_dh():
            return (0, False, "DH already created")

        args = []
        args.append(self.easyrsa)
        # args.append(f"--pki-dir={self._pki_dir}")
        if self.dh_keysize:
            args.append(f"--keysize={self.dh_keysize}")
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append("gen-dh")

        rc, out, err = self._exec(args)

        _out = out.splitlines()
        _err = err.splitlines()
        # self.module.log(msg=f"= _out: {_out} {type(_out)}")
        # self.module.log(msg=f"= _err: {_err} {type(_err)}")
        _output = []
        _output += _out
        _output += _err
        self.module.log(msg=f"= output: {_output}")

        dh_pem_file = "/usr/share/easy-rsa/pki/dh.pem"

        if os.path.exists(dh_pem_file):
            rc = 0
            _output = "dh.pem were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    # ----------------------------------------------------------------------------------------------
    # PRIVATE API - validate
    def validate_pki(self):
        """
        """
        self.module.log(msg="EasyRsa::validate_pki()")

        if os.path.exists(self.pki_dir):
            return True
        else:
            return False

    def validate_ca(self):
        """
        """
        self.module.log(msg="EasyRsa::validate__ca()")

        ca_crt_file = f"{self.pki_dir}/ca.crt"
        ca_key_file = f"{self.pki_dir}/private/ca.key"

        if os.path.exists(ca_crt_file) and os.path.exists(ca_key_file):
            return True
        else:
            return False

    def validate_crl(self):
        """
        """
        self.module.log(msg="EasyRsa::validate__crl()")

        crl_pem_file = f"{self.pki_dir}/crl.pem"

        if os.path.exists(crl_pem_file):
            return True
        else:
            return False

    def validate_dh(self):
        """
        """
        self.module.log(msg="EasyRsa::validate__dh()")

        dh_pem_file = f"{self.pki_dir}/dh.pem"

        if os.path.exists(dh_pem_file):
            return True
        else:
            return False

    def validate_req(self):
        """
        """
        self.module.log(msg="EasyRsa::validate__req()")

        req_file = f"{self.pki_dir}/reqs/{self.req_cn_server}.req"

        if os.path.exists(req_file):
            return True
        else:
            return False

    def validate_sign(self):
        """
        """
        self.module.log(msg="EasyRsa::validate__sign()")

        crt_file = f"{self.pki_dir}/issued/{self.req_cn_server}.crt"

        if os.path.exists(crt_file):
            return True
        else:
            return False

    # ----------------------------------------------------------------------------------------------

    def _exec(self, commands, check_rc=False):
        """
          execute shell program
        """
        self.module.log(msg=f"_exec(commands={commands}, check_rc={check_rc}")

        rc, out, err = self.module.run_command(commands, check_rc=check_rc)

        if int(rc) != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err

    def list_files(self, startpath):
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            self.module.log(msg=f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                self.module.log(msg=f"{subindent}{f}")


def main():

    args = dict(

        pki_dir=dict(
            required=False,
            type="str"
        ),
        force=dict(
            required=False,
            default=False,
            type='bool'
        ),
        req_cn_ca=dict(
            required=False
        ),
        req_cn_server=dict(
            required=False
        ),
        ca_keysize=dict(
            required=False,
            type="int"
        ),
        dh_keysize=dict(
            required=False,
            type="int"
        ),
        working_dir=dict(
            required=False
        ),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    e = EasyRsa(module)
    result = e.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
