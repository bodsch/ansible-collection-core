#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os
import shutil

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.easyrsa import EasyRSA
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: easyrsa
version_added: 1.1.3
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Manage a Public Key Infrastructure (PKI) using EasyRSA.

description:
  - This module allows management of a PKI environment using EasyRSA.
  - It supports initialization of a PKI directory, creation of a Certificate Authority (CA),
    generation of certificate signing requests (CSR), signing of certificates, generation of
    a certificate revocation list (CRL), and generation of Diffie-Hellman (DH) parameters.
  - It is useful for automating the setup of secure communication infrastructure.


options:
  pki_dir:
    description:
      - Path to the PKI directory where certificates and keys will be stored.
    required: false
    type: str

  force:
    description:
      - If set to true, the existing PKI directory will be deleted and recreated.
    required: false
    type: bool
    default: false

  req_cn_ca:
    description:
      - Common Name (CN) to be used for the CA certificate.
    required: false
    type: str

  req_cn_server:
    description:
      - Common Name (CN) to be used for the server certificate request.
    required: false
    type: str

  ca_keysize:
    description:
      - Key size (in bits) for the CA certificate.
    required: false
    type: int

  dh_keysize:
    description:
      - Key size (in bits) for the Diffie-Hellman parameters.
    required: false
    type: int

  working_dir:
    description:
      - Directory in which to execute the EasyRSA commands.
      - If not set, commands will be executed in the current working directory.
    required: false
    type: str

"""

EXAMPLES = r"""
- name: initialize easy-rsa - (this is going to take a long time)
  bodsch.core.easyrsa:
    pki_dir: '{{ openvpn_easyrsa.directory }}/pki'
    req_cn_ca: "{{ openvpn_certificate.req_cn_ca }}"
    req_cn_server: '{{ openvpn_certificate.req_cn_server }}'
    ca_keysize: 4096
    dh_keysize: "{{ openvpn_diffie_hellman_keysize }}"
    working_dir: '{{ openvpn_easyrsa.directory }}'
    force: true
  register: _easyrsa_result
"""

RETURN = r"""
changed:
  description: Indicates whether any changes were made during module execution.
  type: bool
  returned: always

failed:
  description: Indicates whether the module failed.
  type: bool
  returned: always

state:
  description: A detailed list of results from each EasyRSA operation.
  type: list
  elements: dict
  returned: always
  sample:
    - init-pki:
        failed: false
        changed: true
        msg: The PKI was successfully created.
    - build-ca:
        failed: false
        changed: true
        msg: ca.crt and ca.key were successfully created.
    - gen-crl:
        failed: false
        changed: true
        msg: crl.pem was successfully created.
    - gen-req:
        failed: false
        changed: true
        msg: server.req was successfully created.
    - sign-req:
        failed: false
        changed: true
        msg: server.crt was successfully created.
    - gen-dh:
        failed: false
        changed: true
        msg: dh.pem was successfully created.
"""

# ---------------------------------------------------------------------------------------


class EasyRsa(object):
    """ """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        self.state = ""

        self.force = module.params.get("force", False)
        self.pki_dir = module.params.get("pki_dir", None)
        self.req_cn_ca = module.params.get("req_cn_ca", None)
        self.req_cn_server = module.params.get("req_cn_server", None)
        self.ca_keysize = module.params.get("ca_keysize", None)
        self.dh_keysize = module.params.get("dh_keysize", None)
        self.working_dir = module.params.get("working_dir", None)

        self.easyrsa = module.get_bin_path("easyrsa", True)

    def run(self):
        """
        runner
        """
        result_state = []

        if self.working_dir:
            os.chdir(self.working_dir)

        # self.module.log(msg=f"-> pwd : {os.getcwd()}")

        if self.force:
            # self.module.log(msg="force mode ...")
            # self.module.log(msg=f"remove {self.pki_dir}")

            if os.path.isdir(self.pki_dir):
                shutil.rmtree(self.pki_dir)

        ersa = EasyRSA(
            module=self.module,
            force=self.force,
            pki_dir=self.pki_dir,
            req_cn_ca=self.req_cn_ca,
            req_cn_server=self.req_cn_server,
            ca_keysize=self.ca_keysize,
            dh_keysize=self.dh_keysize,
            working_dir=self.working_dir,
        )

        steps = [
            ("init-pki", ersa.create_pki),
            ("build-ca", ersa.build_ca),
            ("gen-crl", ersa.gen_crl),
            ("gen-req", ersa.gen_req),
            ("sign-req", ersa.sign_req),
            ("gen-dh", ersa.gen_dh),
        ]

        for step_name, step_func in steps:
            self.module.log(msg=f"  - {step_name}")
            rc, changed, msg = step_func()

            result_state.append(
                {step_name: {"failed": rc != 0, "changed": changed, "msg": msg}}
            )
            if rc != 0:
                break

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        result = dict(changed=_changed, failed=failed, state=result_state)

        return result

    def list_files(self, startpath):
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, "").count(os.sep)
            indent = " " * 4 * (level)
            self.module.log(msg=f"{indent}{os.path.basename(root)}/")
            subindent = " " * 4 * (level + 1)
            for f in files:
                self.module.log(msg=f"{subindent}{f}")


def main():

    args = dict(
        pki_dir=dict(required=False, type="str"),
        force=dict(required=False, default=False, type="bool"),
        req_cn_ca=dict(required=False),
        req_cn_server=dict(required=False),
        ca_keysize=dict(required=False, type="int"),
        dh_keysize=dict(required=False, type="int"),
        working_dir=dict(required=False),
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
if __name__ == "__main__":
    main()
