#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to create or remove an inline OpenVPN client configuration.

This module builds an inline OpenVPN client configuration file from an
Easy-RSA-style PKI layout. It reads the client private key and certificate,
renders them into a fixed Jinja2 template, writes the resulting ``.ovpn`` file,
and stores a checksum sidecar file for basic change validation. It can also
remove the generated configuration and its checksum file.
"""

# (c) 2022, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import hashlib
import os
import sys

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: openvpn_ovpn
short_description: Create or remove an inline OpenVPN client configuration (.ovpn) from Easy-RSA client credentials
version_added: "1.1.3"
author:
  - Bodo Schulz (@bodsch) <me+ansible@bodsch.me>

description:
  - Creates an inline OpenVPN client configuration file (C(.ovpn)) containing embedded client key and certificate.
  - The client key and certificate are read from an Easy-RSA PKI structure (C(pki/private/<user>.key) and C(pki/issued/<user>.crt)).
  - Uses a Jinja2 template file (C(/etc/openvpn/client.ovpn.template)) to render the final config.
  - Writes a SHA256 checksum sidecar file (C(.<user>.ovpn.sha256)) to support basic change detection.
  - Can remove both the generated C(.ovpn) and checksum file.

options:
  state:
    description:
      - Whether the OVPN configuration should be present or absent.
    type: str
    default: present
    choices:
      - present
      - absent

  force:
    description:
      - If enabled, removes existing destination files before (re)creating the configuration.
      - This also removes the checksum file.
    type: bool
    default: false

  username:
    description:
      - Client name/user to build the configuration for.
      - Used to locate Easy-RSA key/certificate and to name the output files.
    type: str
    required: true

  destination_directory:
    description:
      - Directory where the generated C(<username>.ovpn) and checksum file are written.
      - The directory must exist.
    type: str
    required: true

  chdir:
    description:
      - Change into this directory before processing.
      - Useful if Easy-RSA PKI paths are relative to a working directory.
    type: path
    required: false

  creates:
    description:
      - If this path exists, the module returns early with no changes.
      - When C(state=present) and C(creates) exists, the message will indicate the configuration is already created.
    type: path
    required: false

notes:
  - Check mode is not supported.
  - The template path is currently fixed to C(/etc/openvpn/client.ovpn.template).
  - The module expects an Easy-RSA PKI layout under the (optional) C(chdir) working directory.
  - File permissions for the generated C(.ovpn) are set to C(0600).

requirements:
  - Python Jinja2 must be available on the target node for C(state=present).
"""

EXAMPLES = r"""
- name: Create an inline client configuration for user 'alice'
  bodsch.core.openvpn_ovpn:
    state: present
    username: alice
    destination_directory: /etc/openvpn/clients

- name: Create config with PKI relative to a working directory
  bodsch.core.openvpn_ovpn:
    state: present
    username: bob
    destination_directory: /etc/openvpn/clients
    chdir: /etc/easy-rsa

- name: Force recreation of an existing .ovpn file
  bodsch.core.openvpn_ovpn:
    state: present
    username: carol
    destination_directory: /etc/openvpn/clients
    force: true

- name: Skip if a marker file already exists
  bodsch.core.openvpn_ovpn:
    state: present
    username: dave
    destination_directory: /etc/openvpn/clients
    creates: /var/lib/openvpn/clients/dave.created

- name: Remove client configuration and checksum file
  bodsch.core.openvpn_ovpn:
    state: absent
    username: alice
    destination_directory: /etc/openvpn/clients
"""

RETURN = r"""
changed:
  description:
    - Whether the module changed anything.
  returned: always
  type: bool

failed:
  description:
    - Indicates failure.
  returned: always
  type: bool

message:
  description:
    - Human readable status message.
  returned: always
  type: str
  sample:
    - "ovpn file /etc/openvpn/clients/alice.ovpn exists."
    - "ovpn file successful written as /etc/openvpn/clients/alice.ovpn."
    - "ovpn file /etc/openvpn/clients/alice.ovpn successful removed."
    - "can not find key or certfile for user alice."
    - "user req already created"
"""

# ---------------------------------------------------------------------------------------


class OpenVPNOvpn(object):
    """
    Manage creation and removal of inline OpenVPN client configuration files.

    The class resolves all relevant paths, validates checksum state, creates
    rendered ``.ovpn`` files from client credentials, and removes generated
    artifacts when requested.
    """

    module = None

    def __init__(self, module):
        """
        Initialize the module wrapper and resolve all file paths.

        Args:
            module: Active Ansible module instance providing parameters,
                logging, and result handling.
        """
        self.module = module

        self.state = module.params.get("state")
        self.force = module.params.get("force", False)
        self._username = module.params.get("username", None)
        self._destination_directory = module.params.get("destination_directory", None)

        self._chdir = module.params.get("chdir", None)
        self._creates = module.params.get("creates", None)

        self._openvpn = module.get_bin_path("openvpn", True)
        self._easyrsa = module.get_bin_path("easyrsa", True)

        self.key_file = os.path.join("pki", "private", f"{self._username}.key")
        self.crt_file = os.path.join("pki", "issued", f"{self._username}.crt")
        self.dst_file = os.path.join(
            self._destination_directory, f"{self._username}.ovpn"
        )

        self.dst_checksum_file = os.path.join(
            self._destination_directory, f".{self._username}.ovpn.sha256"
        )

    def run(self):
        """
        Execute the requested module workflow.

        The method optionally changes into the configured working directory,
        validates checksum state, applies force handling, honors the optional
        marker file, and dispatches to the requested present or absent action.

        Returns:
            dict: Result dictionary describing the module outcome.
        """
        result = dict(failed=False, changed=False, ansible_module_results="none")

        if self._chdir:
            os.chdir(self._chdir)

        self.__validate_checksums()

        if self.force:
            self.module.log(msg="force mode ...")
            if os.path.exists(self.dst_file):
                self.module.log(msg=f"remove {self.dst_file}")
                os.remove(self.dst_file)
                os.remove(self.dst_checksum_file)

        if self._creates:
            if os.path.exists(self._creates):
                message = "nothing to do."
                if self.state == "present":
                    message = "user req already created"

                return dict(changed=False, message=message)

        if self.state == "present":
            return self.__create_ovpn_config()
        if self.state == "absent":
            return self.__remove_ovpn_config()

        return result

    def __create_ovpn_config(self):
        """
        Create the inline OpenVPN client configuration file.

        The method reads the client key and certificate from the Easy-RSA PKI,
        renders the fixed client template, writes the resulting ``.ovpn`` file,
        creates the checksum sidecar file, and sets file permissions to
        ``0600``.

        Returns:
            dict: Result dictionary describing whether the configuration was
            created successfully or why creation failed.
        """
        if os.path.exists(self.dst_file):
            return dict(
                failed=False,
                changed=False,
                message=f"ovpn file {self.dst_file} exists.",
            )

        if os.path.exists(self.key_file) and os.path.exists(self.crt_file):
            from jinja2 import Template

            with open(self.key_file, "r") as k_file:
                k_data = k_file.read().rstrip("\n")

            cert = self.__extract_certs_as_strings(self.crt_file)[0].rstrip("\n")

            tpl = "/etc/openvpn/client.ovpn.template"

            with open(tpl) as file_:
                tm = Template(file_.read())

            d = tm.render(key=k_data, cert=cert)

            with open(self.dst_file, "w") as fp:
                fp.write(d)

            self.__create_checksum_file(self.dst_file, self.dst_checksum_file)

            force_mode = "0600"
            if isinstance(force_mode, str):
                mode = int(force_mode, base=8)

            os.chmod(self.dst_file, mode)

            return dict(
                failed=False,
                changed=True,
                message=f"ovpn file successful written as {self.dst_file}.",
            )

        else:
            return dict(
                failed=True,
                changed=False,
                message=f"can not find key or certfile for user {self._username}.",
            )

    def __remove_ovpn_config(self):
        """
        Remove the generated OpenVPN client configuration artifacts.

        The method removes the ``.ovpn`` file, the checksum sidecar file, and
        the optional marker file when present.

        Returns:
            dict: Result dictionary describing the removal outcome.
        """
        if os.path.exists(self.dst_file):
            os.remove(self.dst_file)

        if os.path.exists(self.dst_checksum_file):
            os.remove(self.dst_checksum_file)

        if self._creates and os.path.exists(self._creates):
            os.remove(self._creates)

        return dict(
            failed=False,
            changed=True,
            message=f"ovpn file {self.dst_file} successful removed.",
        )

    def __extract_certs_as_strings(self, cert_file):
        """
        Extract PEM certificate blocks from a certificate file.

        The method parses the file line by line and returns all complete
        certificate blocks as individual strings.

        Args:
            cert_file: Path to the certificate file that may contain one or
                more PEM certificate blocks.

        Returns:
            list: List of PEM certificate strings in the order they were found.
        """
        certs = []
        with open(cert_file) as whole_cert:
            cert_started = False
            content = ""
            for line in whole_cert:
                if "-----BEGIN CERTIFICATE-----" in line:
                    if not cert_started:
                        content += line
                        cert_started = True
                    else:
                        print("Error, start cert found but already started")
                        sys.exit(1)
                elif "-----END CERTIFICATE-----" in line:
                    if cert_started:
                        content += line
                        certs.append(content)
                        content = ""
                        cert_started = False
                    else:
                        print("Error, cert end found without start")
                        sys.exit(1)
                elif cert_started:
                    content += line

            if cert_started:
                print("The file is corrupted")
                sys.exit(1)

        return certs

    def __validate_checksums(self):
        """
        Validate the checksum of the generated client configuration file.

        If the checksum sidecar file is missing but the destination file exists,
        the checksum file is created automatically.

        Returns:
            bool: C(True) when the current checksum matches the stored checksum,
            otherwise C(False).
        """
        dst_checksum = None
        dst_old_checksum = None

        if os.path.exists(self.dst_file):
            with open(self.dst_file, "r") as d:
                dst_data = d.read().rstrip("\n")
                dst_checksum = self.__checksum(dst_data)

        if os.path.exists(self.dst_checksum_file):
            with open(self.dst_checksum_file, "r") as f:
                dst_old_checksum = f.readlines()[0]
        else:
            if dst_checksum is not None:
                dst_old_checksum = self.__create_checksum_file(
                    self.dst_file, self.dst_checksum_file
                )

        if dst_checksum is None or dst_old_checksum is None:
            valid = False
        else:
            valid = dst_checksum == dst_old_checksum

        return valid

    def __create_checksum_file(self, filename, checksumfile):
        """
        Create or update the checksum sidecar file for a given file.

        Args:
            filename: Path to the file whose checksum should be calculated.
            checksumfile: Path to the checksum sidecar file to write.

        Returns:
            str: SHA256 checksum value of the input file content.
        """
        if os.path.exists(filename):
            with open(filename, "r") as d:
                _data = d.read().rstrip("\n")
                _checksum = self.__checksum(_data)

            with open(checksumfile, "w") as f:
                f.write(_checksum)

        return _checksum

    def __checksum(self, plaintext):
        """
        Calculate the SHA256 checksum of a text value.

        Args:
            plaintext: Text value that should be hashed.

        Returns:
            str: Hexadecimal SHA256 digest of the input text.
        """
        _bytes = plaintext.encode("utf-8")
        _hash = hashlib.sha256(_bytes)
        return _hash.hexdigest()


def main():
    """
    Create the Ansible module instance and execute the module workflow.

    The function defines the module argument specification, instantiates the
    module wrapper, executes the requested action, and returns the final result
    to Ansible.
    """
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(default="present", choices=["present", "absent"]),
            force=dict(required=False, default=False, type="bool"),
            username=dict(required=True, type="str"),
            destination_directory=dict(required=True, type="str"),
            chdir=dict(required=False),
            creates=dict(required=False),
        ),
        supports_check_mode=False,
    )

    o = OpenVPNOvpn(module)
    result = o.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
