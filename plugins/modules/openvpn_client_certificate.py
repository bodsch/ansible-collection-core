#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os
import shutil
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum
from ansible_collections.bodsch.core.plugins.module_utils.directory import (
    create_directory,
)
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: openvpn_client_certificate
short_description: Manage OpenVPN client certificates using EasyRSA.
version_added: "1.1.3"
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

description:
  - This module manages OpenVPN client certificates using EasyRSA.
  - It supports the creation and revocation of client certificates.
  - Certificates are tracked via checksums to detect changes.
  - Ideal for automated PKI workflows with OpenVPN infrastructure.

options:
  clients:
    description:
      - A list of client definitions, each representing a certificate to be created or revoked.
    required: true
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - Name of the OpenVPN client.
        required: true
        type: str
      state:
        description:
          - Whether the certificate should exist or be revoked.
        required: false
        default: present
        choices: [present, absent]
        type: str
      roadrunner:
        description:
          - Optional boolean flag, can be used for specific logic in a role.
        required: false
        type: bool
      static_ip:
        description:
          - Static IP address for the client (optional, used in templating).
        required: false
        type: str
      remote:
        description:
          - Remote server address or hostname.
        required: false
        type: str
      port:
        description:
          - Port used by OpenVPN for this client.
        required: false
        type: int
      proto:
        description:
          - Protocol to use (typically UDP or TCP).
        required: false
        type: str
      device:
        description:
          - Network device (usually tun).
        required: false
        type: str
      ping:
        description:
          - Ping interval for the client.
        required: false
        type: int
      ping_restart:
        description:
          - Time before restarting connection after ping timeout.
        required: false
        type: int
      cert:
        description:
          - Certificate file name for the client.
        required: false
        type: str
      key:
        description:
          - Key file name for the client.
        required: false
        type: str
      tls_auth:
        description:
          - TLS authentication settings.
        required: false
        type: dict
        suboptions:
          enabled:
            description:
              - Whether TLS auth is enabled.
            type: bool
            required: false

  force:
    description:
      - If true, the client certificate will be re-created even if it already exists.
    required: false
    type: bool
    default: false

  working_dir:
    description:
      - Path to the EasyRSA working directory.
      - All EasyRSA commands will be executed within this directory.
    required: false
    type: str
"""

EXAMPLES = r"""
- name: create or revoke client certificate
  bodsch.core.openvpn_client_certificate:
    clients:
      - name: molecule
        state: present
        roadrunner: false
        static_ip: 10.8.3.100
        remote: server
        port: 1194
        proto: udp
        device: tun
        ping: 20
        ping_restart: 45
        cert: molecule.crt
        key: molecule.key
        tls_auth:
          enabled: true
      - name: roadrunner_one
        state: present
        roadrunner: true
        static_ip: 10.8.3.10
        remote: server
        port: 1194
        proto: udp
        device: tun
        ping: 20
        ping_restart: 45
        cert: roadrunner_one.crt
        key: roadrunner_one.key
        tls_auth:
          enabled: true
    working_dir: /etc/easy-rsa
  when:
    - openvpn_client_list | default([]) | count > 0
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
  description: List of results per client certificate operation.
  type: list
  elements: dict
  returned: always
  sample:
    - molecule:
        failed: false
        changed: true
        message: The client certificate has been successfully created.
    - roadrunner_one:
        failed: false
        changed: false
        message: The client certificate has already been created.
"""

# ---------------------------------------------------------------------------------------


class OpenVPNClientCertificate(object):
    """ """

    def __init__(self, module):
        """ """
        self.module = module

        self.module.log("OpenVPNClientCertificate::__init__(module)")

        self.state = module.params.get("state")
        self.clients = module.params.get("clients", None)
        self.force = module.params.get("force", False)
        self.working_dir = module.params.get("working_dir", None)

        self.bin_openvpn = module.get_bin_path("openvpn", True)
        self.bin_easyrsa = module.get_bin_path("easyrsa", True)

    def run(self):
        """
        runner
        """
        self.module.log("OpenVPNClientCertificate::run()")

        result_state = []

        self.checksum = Checksum(self.module)

        if self.working_dir:
            os.chdir(self.working_dir)

        for client in self.clients:

            self.module.log(f"  - client: {client}")

            res = {}
            username = client.get("name")
            state = client.get("state", "present")

            self.checksum_directory = f"{Path.home()}/.ansible/cache/openvpn/{username}"

            if state == "absent":
                res[username] = self.revoke_vpn_user(username=username)
            if state == "present":
                if self.force:
                    if os.path.isdir(self.checksum_directory):
                        shutil.rmtree(self.checksum_directory)

                res[username] = self.create_vpn_user(username=username)

            result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        result = dict(changed=_changed, failed=failed, state=result_state)

        return result

    def create_vpn_user(self, username: str):
        """ """
        self.module.log(msg=f"OpenVPNClientCertificate::create_vpn_user({username})")

        self.req_file = os.path.join("pki", "reqs", f"{username}.req")
        self.key_file = os.path.join("pki", "private", f"{username}.key")
        self.crt_file = os.path.join("pki", "issued", f"{username}.crt")

        self.req_checksum_file = os.path.join(self.checksum_directory, "req.sha256")
        self.key_checksum_file = os.path.join(self.checksum_directory, "key.sha256")
        self.crt_checksum_file = os.path.join(self.checksum_directory, "crt.sha256")

        if not self.vpn_user_req(username=username):
            """ """
            create_directory(self.checksum_directory)

            args = []

            # rc = 0
            args.append(self.bin_easyrsa)
            args.append("--batch")
            args.append("build-client-full")
            args.append(username)
            args.append("nopass")

            self.module.log(msg=f"args: {args}")

            rc, out, err = self._exec(args)

            if rc != 0:
                """ """
                return dict(failed=True, changed=False, message=f"{out.rstrip()}")
            else:
                self.write_checksum(
                    file_name=self.req_file, checksum_file=self.req_checksum_file
                )
                self.write_checksum(
                    file_name=self.key_file, checksum_file=self.key_checksum_file
                )
                self.write_checksum(
                    file_name=self.crt_file, checksum_file=self.crt_checksum_file
                )

                return dict(
                    failed=False,
                    changed=True,
                    message="The client certificate has been successfully created.",
                )
        else:
            valid, msg = self.validate_checksums()

            if valid:
                return dict(
                    failed=False,
                    changed=False,
                    message="The client certificate has already been created.",
                )
            else:
                return dict(failed=True, changed=False, message=msg)

    def revoke_vpn_user(self, username: str):
        """ """
        self.module.log(msg=f"OpenVPNClientCertificate::revoke_vpn_user({username})")

        if not self.vpn_user_req():
            return dict(
                failed=False,
                changed=False,
                message=f"There is no certificate request for the user {username}.",
            )

        args = []

        # rc = 0
        args.append(self.bin_easyrsa)
        args.append("--batch")
        args.append("revoke")
        args.append(username)

        rc, out, err = self._exec(args)

        if rc == 0:
            # remove checksums
            os.remove(self.checksum_directory)
            # recreate CRL
            args = []
            args.append(self.bin_easyrsa)
            args.append("gen-crl")

        if os.path.isdir(self.checksum_directory):
            shutil.rmtree(self.checksum_directory)

        return dict(
            changed=True,
            failed=False,
            message=f"The certificate for the user {username} has been revoked successfully.",
        )

    def vpn_user_req(self, username: str):
        """ """
        self.module.log(msg=f"OpenVPNClientCertificate::vpn_user_req({username})")

        req_file = os.path.join("pki", "reqs", f"{username}.req")

        if os.path.exists(req_file):
            return True

        return False

    def validate_checksums(self):
        """ """
        self.module.log(msg="OpenVPNClientCertificate::validate_checksums()")
        msg = ""

        req_changed, req_msg = self.validate(self.req_checksum_file, self.req_file)
        key_changed, key_msg = self.validate(self.req_checksum_file, self.req_file)
        crt_changed, crt_msg = self.validate(self.req_checksum_file, self.req_file)

        if req_changed or key_changed or crt_changed:
            _msg = []

            if req_changed:
                _msg.append(req_msg)
            if key_changed:
                _msg.append(key_msg)
            if crt_changed:
                _msg.append(crt_msg)

            msg = ", ".join(_msg)
            valid = False
        else:
            valid = True
            msg = "All Files are valid."

        return valid, msg

    def validate(self, checksum_file: str, file_name: str):
        """ """
        self.module.log(
            msg=f"OpenVPNClientCertificate::validate({checksum_file}, {file_name})"
        )
        changed = False
        msg = ""

        checksum = None
        old_checksum = None

        changed, checksum, old_checksum = self.checksum.validate_from_file(
            checksum_file, file_name
        )

        if os.path.exists(file_name) and not os.path.exists(checksum_file):
            self.write_checksum(file_name=file_name, checksum_file=checksum_file)
            changed = False

        if changed:
            msg = f"{checksum_file} are changed"

        return (changed, msg)

    def write_checksum(self, file_name: str, checksum_file: str):
        """ """
        self.module.log(
            msg=f"OpenVPNClientCertificate::write_checksum({file_name}, {checksum_file})"
        )

        checksum = self.checksum.checksum_from_file(file_name)
        self.checksum.write_checksum(checksum_file, checksum)

    def _exec(self, commands, check_rc=False):
        """
        execute shell program
        """
        self.module.log(
            msg=f"OpenVPNClientCertificate::_exec(commands={commands}, check_rc={check_rc}"
        )
        rc, out, err = self.module.run_command(commands, check_rc=check_rc)
        return rc, out, err

    def result_values(self, out: str, err: str) -> list:
        """
        " """
        _out = out.splitlines()
        _err = err.splitlines()
        _output = []
        _output += _out
        _output += _err
        # self.module.log(msg=f"= output: {_output}")
        return _output


def main():
    """ """
    args = dict(
        clients=dict(required=True, type="list"),
        force=dict(required=False, default=False, type="bool"),
        working_dir=dict(required=False),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    o = OpenVPNClientCertificate(module)
    result = o.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
