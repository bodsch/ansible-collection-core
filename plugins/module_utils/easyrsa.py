#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, division, print_function)
import os


class EasyRSA():

    """
    """
    def __init__(
        self,
        module: any,
        force: bool = False,
        pki_dir: str = "",
        req_cn_ca: str = "",
        req_cn_server: str = "",
        ca_keysize: int = 4086,
        dh_keysize: int = 2048,
        working_dir: str = "",
    ):
        """
        """
        self.module = module

        self.state = ""

        self.force = module.params.get("force", False)
        self.pki_dir = pki_dir
        self.req_cn_ca = req_cn_ca
        self.req_cn_server = req_cn_server
        self.ca_keysize = ca_keysize
        self.dh_keysize = dh_keysize
        self.working_dir = working_dir

        self.easyrsa = module.get_bin_path('easyrsa', True)

    # ----------------------------------------------------------------------------------------------
    # Public API - create
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
        _output = self.result_values(out, err)

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

        _output = self.result_values(out, err)

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
        _output = self.result_values(out, err)

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
        _output = self.result_values(out, err)

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
        _output = self.result_values(out, err)

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

    def result_values(self, out: str, err: str) -> list:
        """
    "   """
        _out = out.splitlines()
        _err = err.splitlines()
        _output = []
        _output += _out
        _output += _err
        # self.module.log(msg=f"= output: {_output}")
        return _output
