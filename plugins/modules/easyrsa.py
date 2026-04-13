#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to manage an EasyRSA-based Public Key Infrastructure.

This module orchestrates common EasyRSA PKI operations such as PKI
initialization, CA creation, certificate request generation, certificate
signing, CRL generation, and Diffie-Hellman parameter generation.
"""

from __future__ import absolute_import, division, print_function

import os
import shutil
from typing import Any, Dict, List, Optional

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.easyrsa import EasyRSA
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: easyrsa
version_added: "1.1.3"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Manage an EasyRSA-based Public Key Infrastructure.

description:
  - Manage a Public Key Infrastructure (PKI) using EasyRSA.
  - The module can initialize a PKI directory, create a certificate authority,
    generate a certificate revocation list, generate certificate signing
    requests, sign requests, and generate Diffie-Hellman parameters.
  - It is intended for automated PKI bootstrapping and certificate lifecycle
    preparation in infrastructure and VPN environments.

requirements:
  - easyrsa

notes:
  - This module does not support check mode.
  - The module executes multiple EasyRSA steps in a fixed order and stops on
    the first failed step.
  - If O(force=true) is set and the PKI directory exists, it will be removed
    before the PKI is recreated.

options:
  pki_dir:
    description:
      - Absolute or relative path to the PKI directory.
      - Certificates, keys, requests, and related PKI artifacts are stored in
        this directory.
    required: false
    type: str

  force:
    description:
      - Remove an existing PKI directory before recreating it.
      - Use this only when a full PKI rebuild is intended.
    required: false
    type: bool
    default: false

  req_cn_ca:
    description:
      - Common Name to use when creating the certificate authority.
    required: false
    type: str

  req_cn_server:
    description:
      - Common Name to use when generating the server certificate request.
    required: false
    type: str

  ca_keysize:
    description:
      - RSA key size in bits for the certificate authority key.
    required: false
    type: int

  dh_keysize:
    description:
      - RSA key size in bits for Diffie-Hellman parameter generation.
    required: false
    type: int

  working_dir:
    description:
      - Working directory used before executing EasyRSA operations.
      - If omitted, the current process working directory is used.
    required: false
    type: str
"""

EXAMPLES = r"""
- name: Initialize a complete EasyRSA PKI
  bodsch.core.easyrsa:
    pki_dir: "{{ openvpn_easyrsa.directory }}/pki"
    req_cn_ca: "{{ openvpn_certificate.req_cn_ca }}"
    req_cn_server: "{{ openvpn_certificate.req_cn_server }}"
    ca_keysize: 4096
    dh_keysize: "{{ openvpn_diffie_hellman_keysize }}"
    working_dir: "{{ openvpn_easyrsa.directory }}"
    force: true
  register: easyrsa_result

- name: Create PKI without removing an existing directory
  bodsch.core.easyrsa:
    pki_dir: "/etc/openvpn/easy-rsa/pki"
    req_cn_ca: "Example-CA"
    req_cn_server: "vpn.example.org"
    ca_keysize: 4096
    dh_keysize: 2048
    working_dir: "/etc/openvpn/easy-rsa"

- name: Show EasyRSA execution state
  ansible.builtin.debug:
    var: easyrsa_result.state
"""

RETURN = r"""
changed:
  description:
    - Indicates whether at least one EasyRSA step changed the managed state.
  returned: always
  type: bool
  sample: true

failed:
  description:
    - Indicates whether the module execution failed.
  returned: always
  type: bool
  sample: false

state:
  description:
    - Ordered list with the result of each executed EasyRSA step.
    - Every entry contains the step name and a result object with C(failed),
      C(changed), and C(msg).
  returned: always
  type: list
  elements: dict
  sample:
    - init-pki:
        failed: false
        changed: true
        msg: "The PKI was successfully created."
    - build-ca:
        failed: false
        changed: true
        msg: "ca.crt and ca.key were successfully created."
    - gen-crl:
        failed: false
        changed: true
        msg: "crl.pem was successfully created."
    - gen-req:
        failed: false
        changed: true
        msg: "server.req was successfully created."
    - sign-req:
        failed: false
        changed: true
        msg: "server.crt was successfully created."
    - gen-dh:
        failed: false
        changed: true
        msg: "dh.pem was successfully created."
"""

# ---------------------------------------------------------------------------------------


class EasyRsa:
    """
    Coordinate EasyRSA PKI operations for the Ansible module.

    The class reads module parameters, prepares the execution environment,
    invokes the underlying EasyRSA helper implementation, and aggregates the
    step results into the final Ansible module response.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the EasyRSA module wrapper.

        Args:
            module: Active Ansible module instance containing parameters and
                logging helpers.
        """
        self.module = module

        self.state: str = ""

        self.force: bool = module.params.get("force", False)
        self.pki_dir: Optional[str] = module.params.get("pki_dir", None)
        self.req_cn_ca: Optional[str] = module.params.get("req_cn_ca", None)
        self.req_cn_server: Optional[str] = module.params.get("req_cn_server", None)
        self.ca_keysize: Optional[int] = module.params.get("ca_keysize", None)
        self.dh_keysize: Optional[int] = module.params.get("dh_keysize", None)
        self.working_dir: Optional[str] = module.params.get("working_dir", None)

        self.easyrsa: Optional[str] = module.get_bin_path("easyrsa", True)

    def run(self) -> Dict[str, Any]:
        """
        Execute the EasyRSA workflow.

        The method optionally switches into the configured working directory,
        removes the existing PKI directory when C(force) is enabled, and then
        executes the EasyRSA steps in a fixed sequence.

        Returns:
            Final Ansible result dictionary containing C(changed), C(failed),
            and C(state).
        """
        result_state: List[Dict[str, Dict[str, Any]]] = []

        if self.working_dir:
            os.chdir(self.working_dir)

        if self.force and self.pki_dir and os.path.isdir(self.pki_dir):
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

        result: Dict[str, Any] = {
            "changed": _changed,
            "failed": failed,
            "state": result_state,
        }

        return result

    def list_files(self, startpath: str) -> None:
        """
        Log a recursive directory tree for debugging purposes.

        Args:
            startpath: Root directory that should be traversed and logged.
        """
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, "").count(os.sep)
            indent = " " * 4 * level
            self.module.log(msg=f"{indent}{os.path.basename(root)}/")
            subindent = " " * 4 * (level + 1)
            for file_name in files:
                self.module.log(msg=f"{subindent}{file_name}")


def main() -> None:
    """
    Create the Ansible module instance and execute the EasyRSA workflow.
    """
    args = dict(
        pki_dir=dict(required=False, type="str"),
        force=dict(required=False, default=False, type="bool"),
        req_cn_ca=dict(required=False, type="str"),
        req_cn_server=dict(required=False, type="str"),
        ca_keysize=dict(required=False, type="int"),
        dh_keysize=dict(required=False, type="int"),
        working_dir=dict(required=False, type="str"),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    easyrsa = EasyRsa(module)
    result = easyrsa.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
