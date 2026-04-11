#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to manage OpenVPN client certificates with EasyRSA.

The module creates or revokes client certificates in an EasyRSA PKI and keeps
per-client checksum files to validate the generated request, private key, and
certificate files. The public API of the module is intentionally small and
centers around the ``OpenVPNClientCertificate`` class and its ``run()`` method.
"""

from __future__ import absolute_import, division, print_function

import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

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
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

description:
  - Manage OpenVPN client certificates in an EasyRSA-based PKI.
  - The module can create or revoke client certificates for multiple clients in
    a single run.
  - Generated request, private key, and certificate files are tracked with
    checksums to detect unexpected changes.
  - The module is intended for automated OpenVPN PKI workflows.

requirements:
  - easyrsa
  - openvpn

attributes:
  check_mode:
    support: none

notes:
  - This module does not support check mode.
  - Client processing stops only per client operation; all client definitions in
    O(clients) are evaluated and aggregated in the result.
  - If O(force=true) is used for a present client, the module attempts to revoke
    the existing certificate, regenerate the CRL, remove local artifacts, and
    recreate the client certificate.

options:
  clients:
    description:
      - List of OpenVPN client definitions.
      - Each client entry controls whether a certificate should be present or
        absent.
    required: true
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - Name of the OpenVPN client.
          - This value is used as the EasyRSA certificate common name.
        required: true
        type: str
      state:
        description:
          - Desired state of the client certificate.
        required: false
        default: present
        choices:
          - present
          - absent
        type: str
      roadrunner:
        description:
          - Optional role-specific flag.
          - The module does not interpret this value directly.
        required: false
        type: bool
      static_ip:
        description:
          - Optional static IP address for the client.
          - The module does not interpret this value directly.
        required: false
        type: str
      remote:
        description:
          - Optional remote hostname or address for the client.
          - The module does not interpret this value directly.
        required: false
        type: str
      port:
        description:
          - Optional OpenVPN port for the client.
          - The module does not interpret this value directly.
        required: false
        type: int
      proto:
        description:
          - Optional OpenVPN protocol for the client.
          - The module does not interpret this value directly.
        required: false
        type: str
      device:
        description:
          - Optional OpenVPN device name.
          - The module does not interpret this value directly.
        required: false
        type: str
      ping:
        description:
          - Optional ping interval.
          - The module does not interpret this value directly.
        required: false
        type: int
      ping_restart:
        description:
          - Optional ping restart interval.
          - The module does not interpret this value directly.
        required: false
        type: int
      cert:
        description:
          - Optional certificate filename hint.
          - The module does not interpret this value directly.
        required: false
        type: str
      key:
        description:
          - Optional private key filename hint.
          - The module does not interpret this value directly.
        required: false
        type: str
      tls_auth:
        description:
          - Optional TLS authentication settings.
          - The module does not interpret this value directly.
        required: false
        type: dict
        suboptions:
          enabled:
            description:
              - Whether TLS authentication is enabled.
            required: false
            type: bool

  force:
    description:
      - Recreate an existing client certificate when set to C(true).
      - The module revokes the existing certificate, regenerates the CRL,
        removes local client artifacts, and then creates a new certificate.
    required: false
    type: bool
    default: false

  working_dir:
    description:
      - EasyRSA working directory.
      - All EasyRSA commands are executed from this directory.
    required: false
    type: str
"""

EXAMPLES = r"""
- name: Create or revoke client certificates
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
      - name: old_client
        state: absent
    working_dir: /etc/easy-rsa
  register: openvpn_client_certificates

- name: Recreate an existing certificate
  bodsch.core.openvpn_client_certificate:
    clients:
      - name: laptop01
        state: present
    force: true
    working_dir: /etc/easy-rsa

- name: Show per-client results
  ansible.builtin.debug:
    var: openvpn_client_certificates.state
"""

RETURN = r"""
changed:
  description:
    - Indicates whether any client certificate operation changed the managed host.
  type: bool
  returned: always
  sample: true

failed:
  description:
    - Indicates whether one or more client operations failed.
  type: bool
  returned: always
  sample: false

state:
  description:
    - List of per-client result objects.
    - Each entry contains the client name as the key and a result dictionary
      with C(failed), C(changed), and C(message).
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
    - old_client:
        failed: false
        changed: true
        message: The certificate for the user old_client has been revoked successfully.
"""

# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClientPaths:
    """
    Hold all filesystem paths related to a single client certificate.
    """

    username: str
    checksum_directory: str
    req_file: str
    key_file: str
    crt_file: str
    req_checksum_file: str
    key_checksum_file: str
    crt_checksum_file: str


class OpenVPNClientCertificate:
    """
    Manage OpenVPN client certificates using EasyRSA.

    The class provides a small public API for certificate lifecycle operations
    and delegates implementation details to internal helper methods.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the module wrapper and resolve the required binaries.

        Args:
            module: Active Ansible module instance.
        """
        self.module = module

        self.module.log("OpenVPNClientCertificate::__init__(module)")

        self.clients: List[Dict[str, Any]] = module.params.get("clients", []) or []
        self.force: bool = bool(module.params.get("force", False))
        self.working_dir: Optional[str] = module.params.get("working_dir", None)

        self.checksum = Checksum(self.module)

        # Keep both binary lookups to preserve the current runtime contract.
        self.bin_openvpn: str = module.get_bin_path("openvpn", True)
        self.bin_easyrsa: str = module.get_bin_path("easyrsa", True)

        self.checksum_directory: str = ""
        self.req_file: str = ""
        self.key_file: str = ""
        self.crt_file: str = ""
        self.req_checksum_file: str = ""
        self.key_checksum_file: str = ""
        self.crt_checksum_file: str = ""

    def run(self) -> Dict[str, Any]:
        """
        Execute the requested certificate operations for all configured clients.

        Returns:
            Aggregated Ansible result dictionary containing C(changed),
            C(failed), and C(state).
        """
        self.module.log("OpenVPNClientCertificate::run()")

        result_state: List[Dict[str, Dict[str, Any]]] = []

        with self._working_directory():
            for client in self.clients:
                self.module.log(msg=f"  - client: {client}")

                username = str(client.get("name", "")).strip()
                state = str(client.get("state", "present")).strip().lower()

                if not username:
                    result_state.append(
                        {
                            "<invalid>": {
                                "failed": True,
                                "changed": False,
                                "message": "Client definition is missing the required 'name' value.",
                            }
                        }
                    )
                    continue

                if state not in {"present", "absent"}:
                    result_state.append(
                        {
                            username: {
                                "failed": True,
                                "changed": False,
                                "message": f"Unsupported client state '{state}'.",
                            }
                        }
                    )
                    continue

                if state == "absent":
                    client_result = self.revoke_vpn_user(username=username)
                else:
                    client_result = self.create_vpn_user(username=username)

                result_state.append({username: client_result})

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        return {
            "changed": _changed,
            "failed": failed,
            "state": result_state,
        }

    def create_vpn_user(self, username: str) -> Dict[str, Any]:
        """
        Create or validate a client certificate.

        If C(force) is enabled and the client already exists, the existing
        certificate is revoked and local artifacts are removed before the client
        certificate is recreated.

        Args:
            username: Client name used as EasyRSA common name.

        Returns:
            Per-client result dictionary containing C(failed), C(changed), and
            C(message).
        """
        self.module.log(msg=f"OpenVPNClientCertificate::create_vpn_user({username})")

        paths = self._set_client_paths(username)

        if self.force and self.vpn_user_req(username=username):
            revoke_result = self._force_recreate_client(paths)
            if revoke_result is not None:
                return revoke_result

        if not self.vpn_user_req(username=username):
            create_directory(paths.checksum_directory)

            args: List[str] = [
                self.bin_easyrsa,
                "--batch",
                "build-client-full",
                username,
                "nopass",
            ]

            self.module.log(msg=f"args: {args}")

            rc, out, err = self._exec(args)

            if rc != 0:
                return {
                    "failed": True,
                    "changed": False,
                    "message": self._command_message(out, err),
                }

            self.write_checksum(
                file_name=paths.req_file,
                checksum_file=paths.req_checksum_file,
            )
            self.write_checksum(
                file_name=paths.key_file,
                checksum_file=paths.key_checksum_file,
            )
            self.write_checksum(
                file_name=paths.crt_file,
                checksum_file=paths.crt_checksum_file,
            )

            return {
                "failed": False,
                "changed": True,
                "message": "The client certificate has been successfully created.",
            }

        valid, msg = self.validate_checksums()

        if valid:
            return {
                "failed": False,
                "changed": False,
                "message": "The client certificate has already been created.",
            }

        return {
            "failed": True,
            "changed": False,
            "message": msg,
        }

    def revoke_vpn_user(self, username: str) -> Dict[str, Any]:
        """
        Revoke an existing client certificate and regenerate the CRL.

        Args:
            username: Client name used as EasyRSA common name.

        Returns:
            Per-client result dictionary containing C(failed), C(changed), and
            C(message).
        """
        self.module.log(msg=f"OpenVPNClientCertificate::revoke_vpn_user({username})")

        paths = self._set_client_paths(username)

        if not self.vpn_user_req(username=username):
            if os.path.isdir(paths.checksum_directory):
                shutil.rmtree(paths.checksum_directory)

            return {
                "failed": False,
                "changed": False,
                "message": f"There is no certificate request for the user {username}.",
            }

        revoke_args: List[str] = [
            self.bin_easyrsa,
            "--batch",
            "revoke",
            username,
        ]

        rc, out, err = self._exec(revoke_args)
        if rc != 0:
            return {
                "failed": True,
                "changed": False,
                "message": self._command_message(out, err),
            }

        crl_result = self._generate_crl()
        if crl_result is not None:
            return crl_result

        self._remove_client_cache(paths)

        return {
            "changed": True,
            "failed": False,
            "message": f"The certificate for the user {username} has been revoked successfully.",
        }

    def vpn_user_req(self, username: str) -> bool:
        """
        Check whether the client request file exists.

        Args:
            username: Client name used as EasyRSA common name.

        Returns:
            C(True) if the request file exists, otherwise C(False).
        """
        self.module.log(msg=f"OpenVPNClientCertificate::vpn_user_req({username})")

        req_file = os.path.join("pki", "reqs", f"{username}.req")
        return os.path.exists(req_file)

    def validate_checksums(self) -> Tuple[bool, str]:
        """
        Validate all tracked checksum files for the current client context.

        Returns:
            Tuple containing a validation status and a human-readable message.
            The boolean is C(True) when all tracked files are valid.
        """
        self.module.log(msg="OpenVPNClientCertificate::validate_checksums()")

        req_changed, req_msg = self.validate(self.req_checksum_file, self.req_file)
        key_changed, key_msg = self.validate(self.key_checksum_file, self.key_file)
        crt_changed, crt_msg = self.validate(self.crt_checksum_file, self.crt_file)

        if req_changed or key_changed or crt_changed:
            messages: List[str] = []

            if req_changed and req_msg:
                messages.append(req_msg)
            if key_changed and key_msg:
                messages.append(key_msg)
            if crt_changed and crt_msg:
                messages.append(crt_msg)

            return False, ", ".join(messages)

        return True, "All files are valid."

    def validate(self, checksum_file: str, file_name: str) -> Tuple[bool, str]:
        """
        Validate a file against its checksum file.

        Args:
            checksum_file: Path to the checksum file.
            file_name: Path to the tracked file.

        Returns:
            Tuple containing a change flag and a message.
            The boolean is C(True) when the file is missing or its checksum
            differs from the stored value.
        """
        self.module.log(
            msg=f"OpenVPNClientCertificate::validate({checksum_file}, {file_name})"
        )

        if not os.path.exists(file_name):
            return True, f"{file_name} is missing."

        changed, checksum, old_checksum = self.checksum.validate_from_file(
            checksum_file, file_name
        )

        if os.path.exists(file_name) and not os.path.exists(checksum_file):
            self.write_checksum(file_name=file_name, checksum_file=checksum_file)
            return False, ""

        if changed:
            return True, f"{file_name} has changed."

        return False, ""

    def write_checksum(self, file_name: str, checksum_file: str) -> None:
        """
        Write a checksum file for the given tracked file.

        Args:
            file_name: Path to the tracked file.
            checksum_file: Path to the checksum file that should be written.
        """
        self.module.log(
            msg=f"OpenVPNClientCertificate::write_checksum({file_name}, {checksum_file})"
        )

        checksum_directory = os.path.dirname(checksum_file)
        if checksum_directory:
            create_directory(checksum_directory)

        checksum = self.checksum.checksum_from_file(file_name)
        self.checksum.write_checksum(checksum_file, checksum)

    def _exec(
        self,
        commands: Sequence[str],
        check_rc: bool = False,
    ) -> Tuple[int, str, str]:
        """
        Execute an external command using the Ansible module helper.

        Args:
            commands: Command and argument sequence.
            check_rc: Whether C(run_command) should raise on non-zero exit codes.

        Returns:
            Tuple containing return code, stdout, and stderr.
        """
        self.module.log(
            msg=f"OpenVPNClientCertificate::_exec(commands={list(commands)}, check_rc={check_rc})"
        )
        rc, out, err = self.module.run_command(list(commands), check_rc=check_rc)
        return rc, out, err

    def result_values(self, out: str, err: str) -> List[str]:
        """
        Merge stdout and stderr into a single line-based result list.

        Args:
            out: Standard output string.
            err: Standard error string.

        Returns:
            Combined output lines from stdout and stderr.
        """
        output: List[str] = []
        output.extend(out.splitlines())
        output.extend(err.splitlines())
        return output

    def _set_client_paths(self, username: str) -> ClientPaths:
        """
        Build and store the current client path context.

        Args:
            username: Client name used as EasyRSA common name.

        Returns:
            Immutable path container for the client.
        """
        checksum_directory = str(
            Path.home() / ".ansible" / "cache" / "openvpn" / username
        )

        paths = ClientPaths(
            username=username,
            checksum_directory=checksum_directory,
            req_file=os.path.join("pki", "reqs", f"{username}.req"),
            key_file=os.path.join("pki", "private", f"{username}.key"),
            crt_file=os.path.join("pki", "issued", f"{username}.crt"),
            req_checksum_file=os.path.join(checksum_directory, "req.sha256"),
            key_checksum_file=os.path.join(checksum_directory, "key.sha256"),
            crt_checksum_file=os.path.join(checksum_directory, "crt.sha256"),
        )

        self.checksum_directory = paths.checksum_directory
        self.req_file = paths.req_file
        self.key_file = paths.key_file
        self.crt_file = paths.crt_file
        self.req_checksum_file = paths.req_checksum_file
        self.key_checksum_file = paths.key_checksum_file
        self.crt_checksum_file = paths.crt_checksum_file

        return paths

    @contextmanager
    def _working_directory(self) -> Iterator[None]:
        """
        Temporarily switch into the configured EasyRSA working directory.

        Yields:
            None. The context only controls the current working directory.
        """
        if not self.working_dir:
            yield
            return

        current_directory = os.getcwd()
        os.chdir(self.working_dir)
        try:
            yield
        finally:
            os.chdir(current_directory)

    def _force_recreate_client(self, paths: ClientPaths) -> Optional[Dict[str, Any]]:
        """
        Revoke and clean up an existing client certificate before recreation.

        Args:
            paths: Filesystem paths for the current client.

        Returns:
            Failure result dictionary when the recreation preparation fails,
            otherwise C(None).
        """
        revoke_result = self.revoke_vpn_user(paths.username)
        if revoke_result.get("failed", False):
            return revoke_result

        self._remove_client_artifacts(paths)
        return None

    def _remove_client_artifacts(self, paths: ClientPaths) -> None:
        """
        Remove local client artifacts and checksum cache files.

        Args:
            paths: Filesystem paths for the current client.
        """
        for file_name in (paths.req_file, paths.key_file, paths.crt_file):
            if os.path.exists(file_name):
                os.remove(file_name)

        self._remove_client_cache(paths)

    def _remove_client_cache(self, paths: ClientPaths) -> None:
        """
        Remove the checksum cache directory of a client if it exists.

        Args:
            paths: Filesystem paths for the current client.
        """
        if os.path.isdir(paths.checksum_directory):
            shutil.rmtree(paths.checksum_directory)

    def _generate_crl(self) -> Optional[Dict[str, Any]]:
        """
        Regenerate the certificate revocation list.

        Returns:
            Failure result dictionary when CRL generation fails, otherwise
            C(None).
        """
        crl_args: List[str] = [self.bin_easyrsa, "gen-crl"]
        rc, out, err = self._exec(crl_args)

        if rc != 0:
            return {
                "changed": True,
                "failed": True,
                "message": self._command_message(out, err),
            }

        return None

    def _command_message(self, out: str, err: str) -> str:
        """
        Build a normalized error or status message from command output.

        Args:
            out: Standard output string.
            err: Standard error string.

        Returns:
            Normalized single-line message.
        """
        lines = [line.strip() for line in self.result_values(out, err) if line.strip()]
        return " | ".join(lines) if lines else "The command failed without output."


def main() -> None:
    """
    Create the Ansible module instance, execute the workflow, and return the
    aggregated result.
    """
    args = dict(
        clients=dict(required=True, type="list"),
        force=dict(required=False, default=False, type="bool"),
        working_dir=dict(required=False, type="str"),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    module_wrapper = OpenVPNClientCertificate(module)
    result = module_wrapper.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
