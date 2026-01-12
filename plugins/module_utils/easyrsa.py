#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import os
from typing import Any, List, Sequence, Tuple, Union

EasyRSAResult = Tuple[int, bool, Union[str, List[str]]]
ExecResult = Tuple[int, str, str]


class EasyRSA:
    """
    Thin wrapper around the `easyrsa` CLI to manage a simple PKI lifecycle.

    The class is designed to be used from an Ansible context (``module``),
    relying on the module to provide:
      - ``module.params`` for runtime parameters (e.g. ``force``)
      - ``module.log(...)`` for logging
      - ``module.get_bin_path("easyrsa", required=True)`` to locate the binary
      - ``module.run_command([...])`` to execute commands

    Attributes:
        module: Ansible module-like object providing logging and command execution.
        state: Internal state placeholder (currently unused).
        force: Whether to force actions (read from ``module.params['force']``).
        pki_dir: Path to the PKI directory (commonly ``/etc/easy-rsa/pki``).
        req_cn_ca: Common name (CN) used when building the CA.
        req_cn_server: Common name (CN) used for server requests/certificates.
        ca_keysize: RSA key size for CA key generation.
        dh_keysize: DH parameter size for DH generation.
        working_dir: Working directory context (currently not used for chdir).
        easyrsa: Resolved path to the ``easyrsa`` executable.
        easyrsa_directory: Base directory used by some file existence checks
            (defaults to ``/etc/easy-rsa``).
    """

    def __init__(
        self,
        module: Any,
        force: bool = False,
        pki_dir: str = "",
        req_cn_ca: str = "",
        req_cn_server: str = "",
        ca_keysize: int = 4086,
        dh_keysize: int = 2048,
        working_dir: str = "",
    ) -> None:
        """
        Create an EasyRSA helper instance.

        Args:
            module: Ansible module-like object used for logging and running commands.
            force: Optional force flag (note: the effective value is read from
                ``module.params.get("force", False)``).
            pki_dir: Path to PKI directory (e.g. ``/etc/easy-rsa/pki``).
            req_cn_ca: CA request common name (CN) used for ``build-ca``.
            req_cn_server: Server common name (CN) used for ``gen-req`` and ``sign-req``.
            ca_keysize: RSA key size for the CA.
            dh_keysize: DH parameter size.
            working_dir: Intended working directory for running commands (not applied).

        Returns:
            None
        """
        self.module = module

        self.module.log(
            "EasyRSA::__init__("
            f"force={force}, pki_dir={pki_dir}, "
            f"req_cn_ca={req_cn_ca}, req_cn_server={req_cn_server}, "
            f"ca_keysize={ca_keysize}, dh_keysize={dh_keysize}, "
            f"working_dir={working_dir}"
            ")"
        )

        self.state = ""

        self.force = module.params.get("force", False)
        self.pki_dir = pki_dir
        self.req_cn_ca = req_cn_ca
        self.req_cn_server = req_cn_server
        self.ca_keysize = ca_keysize
        self.dh_keysize = dh_keysize
        self.working_dir = working_dir

        self.easyrsa = module.get_bin_path("easyrsa", True)

        self.easyrsa_directory = "/etc/easy-rsa"

    # ----------------------------------------------------------------------------------------------
    # Public API - create
    def create_pki(self) -> Tuple[int, bool, str]:
        """
        Initialize the PKI directory via ``easyrsa init-pki``.

        The method performs an idempotency check using :meth:`validate_pki` and
        returns unchanged when the PKI directory already exists.

        Returns:
            tuple[int, bool, str]: (rc, changed, message)
                rc: 0 on success, non-zero on failure.
                changed: True if the PKI was created, False if it already existed.
                message: Human-readable status message.
        """
        self.module.log(msg="EasyRsa::create_pki()")

        if self.validate_pki():
            return (0, False, "PKI already created")

        args: List[str] = []
        args.append(self.easyrsa)
        args.append("init-pki")

        rc, out, err = self._exec(args)

        if self.validate_pki():
            return (0, True, "The PKI was successfully created.")
        else:
            return (1, True, "An error occurred while creating the PKI.")

    def build_ca(self) -> EasyRSAResult:
        """
        Build a new certificate authority (CA) via ``easyrsa build-ca nopass``.

        Performs an idempotency check using :meth:`validate_ca`. When the CA does not
        exist, this runs Easy-RSA in batch mode and checks for the existence of:
          - ``<easyrsa_directory>/pki/ca.crt``
          - ``<easyrsa_directory>/pki/private/ca.key``

        Returns:
            tuple[int, bool, Union[str, list[str]]]: (rc, changed, output)
                rc: 0 on success; 3 if expected files were not created; otherwise
                    the underlying command return code.
                changed: False if the CA already existed; True if a build was attempted.
                output: Combined stdout/stderr lines (list[str]) or a success message (str).
        """
        if self.validate_ca():
            return (0, False, "CA already created")

        args: List[str] = []
        args.append(self.easyrsa)
        args.append("--batch")
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append(f"--req-cn={self.req_cn_ca}")

        if self.ca_keysize:
            args.append(f"--keysize={self.ca_keysize}")
        args.append("build-ca")
        args.append("nopass")

        rc, out, err = self._exec(args)
        _output: Union[str, List[str]] = self.result_values(out, err)

        ca_crt_file = os.path.join(self.easyrsa_directory, "pki", "ca.crt")
        ca_key_file = os.path.join(self.easyrsa_directory, "pki", "private", "ca.key")

        if os.path.exists(ca_crt_file) and os.path.exists(ca_key_file):
            rc = 0
            _output = "ca.crt and ca.key were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def gen_crl(self) -> EasyRSAResult:
        """
        Generate a certificate revocation list (CRL) via ``easyrsa gen-crl``.

        Performs an idempotency check using :meth:`validate_crl` and checks for
        ``<easyrsa_directory>/pki/crl.pem`` after execution.

        Returns:
            tuple[int, bool, Union[str, list[str]]]: (rc, changed, output)
                rc: 0 on success; 3 if expected file was not created; otherwise
                    the underlying command return code.
                changed: False if CRL already existed; True if generation was attempted.
                output: Combined stdout/stderr lines (list[str]) or a success message (str).
        """
        self.module.log("EasyRSA::gen_crl()")

        if self.validate_crl():
            return (0, False, "CRL already created")

        args: List[str] = []
        args.append(self.easyrsa)
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append("gen-crl")

        rc, out, err = self._exec(args)

        # self.module.log(f" rc : {rc}")
        # self.module.log(f" out: {out}")
        # self.module.log(f" err: {err}")

        _output: Union[str, List[str]] = self.result_values(out, err)

        crl_pem_file = os.path.join(self.easyrsa_directory, "pki", "crl.pem")

        if os.path.exists(crl_pem_file):
            rc = 0
            _output = "crl.pem were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def gen_req(self) -> EasyRSAResult:
        """
        Generate a private key and certificate signing request (CSR) via
        ``easyrsa gen-req <req_cn_server> nopass``.

        Performs an idempotency check using :meth:`validate_req` and checks for:
          - ``<easyrsa_directory>/pki/reqs/<req_cn_server>.req`` after execution.

        Returns:
            tuple[int, bool, Union[str, list[str]]]: (rc, changed, output)
                rc: 0 on success; 3 if expected file was not created; otherwise
                    the underlying command return code.
                changed: False if request already existed; True if generation was attempted.
                output: Combined stdout/stderr lines (list[str]) or a success message (str).
        """
        if self.validate_req():
            return (0, False, "keypair and request already created")

        args: List[str] = []
        args.append(self.easyrsa)
        args.append("--batch")
        # args.append(f"--pki-dir={self._pki_dir}")
        if self.req_cn_ca:
            args.append(f"--req-cn={self.req_cn_ca}")
        args.append("gen-req")
        args.append(self.req_cn_server)
        args.append("nopass")

        rc, out, err = self._exec(args)
        _output: Union[str, List[str]] = self.result_values(out, err)

        req_file = os.path.join(
            self.easyrsa_directory, "pki", "reqs", f"{self.req_cn_server}.req"
        )

        if os.path.exists(req_file):
            rc = 0
            _output = f"{self.req_cn_server}.req were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def sign_req(self) -> EasyRSAResult:
        """
        Sign the server request and generate a certificate via
        ``easyrsa sign-req server <req_cn_server>``.

        Performs an idempotency check using :meth:`validate_sign` and checks for:
          - ``<easyrsa_directory>/pki/issued/<req_cn_server>.crt`` after execution.

        Returns:
            tuple[int, bool, Union[str, list[str]]]: (rc, changed, output)
                rc: 0 on success; 3 if expected file was not created; otherwise
                    the underlying command return code.
                changed: False if the certificate already existed; True if signing was attempted.
                output: Combined stdout/stderr lines (list[str]) or a success message (str).
        """
        if self.validate_sign():
            return (0, False, "certificate alread signed")

        args: List[str] = []
        args.append(self.easyrsa)
        args.append("--batch")
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append("sign-req")
        args.append("server")
        args.append(self.req_cn_server)

        rc, out, err = self._exec(args)
        _output: Union[str, List[str]] = self.result_values(out, err)

        crt_file = os.path.join(
            self.easyrsa_directory, "pki", "issued", f"{self.req_cn_server}.crt"
        )

        if os.path.exists(crt_file):
            rc = 0
            _output = f"{self.req_cn_server}.crt were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    def gen_dh(self) -> EasyRSAResult:
        """
        Generate Diffie-Hellman parameters via ``easyrsa gen-dh``.

        Performs an idempotency check using :meth:`validate_dh` and checks for:
          - ``<easyrsa_directory>/pki/dh.pem`` after execution.

        Returns:
            tuple[int, bool, Union[str, list[str]]]: (rc, changed, output)
                rc: 0 on success; 3 if expected file was not created; otherwise
                    the underlying command return code.
                changed: False if DH params already existed; True if generation was attempted.
                output: Combined stdout/stderr lines (list[str]) or a success message (str).
        """
        if self.validate_dh():
            return (0, False, "DH already created")

        args: List[str] = []
        args.append(self.easyrsa)
        # args.append(f"--pki-dir={self._pki_dir}")
        if self.dh_keysize:
            args.append(f"--keysize={self.dh_keysize}")
        # args.append(f"--pki-dir={self._pki_dir}")
        args.append("gen-dh")

        rc, out, err = self._exec(args)
        _output: Union[str, List[str]] = self.result_values(out, err)

        dh_pem_file = os.path.join(self.easyrsa_directory, "pki", "dh.pem")

        if os.path.exists(dh_pem_file):
            rc = 0
            _output = "dh.pem were successfully created."
        else:
            rc = 3

        return (rc, True, _output)

    # ----------------------------------------------------------------------------------------------
    # PRIVATE API - validate
    def validate_pki(self) -> bool:
        """
        Check whether the PKI directory exists.

        Returns:
            bool: True if ``self.pki_dir`` exists on disk, otherwise False.
        """
        self.module.log(msg="EasyRsa::validate_pki()")

        if os.path.exists(self.pki_dir):
            return True
        else:
            return False

    def validate_ca(self) -> bool:
        """
        Check whether the CA certificate and key exist.

        Expected files (relative to ``self.pki_dir``):
          - ``ca.crt``
          - ``private/ca.key``

        Returns:
            bool: True if both CA files exist, otherwise False.
        """
        self.module.log(msg="EasyRsa::validate__ca()")

        ca_crt_file = os.path.join(self.pki_dir, "ca.crt")
        ca_key_file = os.path.join(self.pki_dir, "private", "ca.key")

        if os.path.exists(ca_crt_file) and os.path.exists(ca_key_file):
            return True
        else:
            return False

    def validate_crl(self) -> bool:
        """
        Check whether the CRL exists.

        Expected file (relative to ``self.pki_dir``):
          - ``crl.pem``

        Returns:
            bool: True if CRL exists, otherwise False.
        """
        self.module.log(msg="EasyRsa::validate__crl()")

        crl_pem_file = os.path.join(self.pki_dir, "crl.pem")

        if os.path.exists(crl_pem_file):
            return True
        else:
            return False

    def validate_dh(self) -> bool:
        """
        Check whether the DH parameters file exists.

        Expected file (relative to ``self.pki_dir``):
          - ``dh.pem``

        Returns:
            bool: True if DH params exist, otherwise False.
        """
        self.module.log(msg="EasyRsa::validate__dh()")

        dh_pem_file = os.path.join(self.pki_dir, "dh.pem")

        if os.path.exists(dh_pem_file):
            return True
        else:
            return False

    def validate_req(self) -> bool:
        """
        Check whether the server request (CSR) exists.

        Expected file (relative to ``self.pki_dir``):
          - ``reqs/<req_cn_server>.req``

        Returns:
            bool: True if the CSR exists, otherwise False.
        """
        self.module.log(msg="EasyRsa::validate__req()")

        req_file = os.path.join(self.pki_dir, "reqs", f"{self.req_cn_server}.req")

        if os.path.exists(req_file):
            return True
        else:
            return False

    def validate_sign(self) -> bool:
        """
        Check whether the signed server certificate exists.

        Expected file (relative to ``self.pki_dir``):
          - ``issued/<req_cn_server>.crt``

        Returns:
            bool: True if the certificate exists, otherwise False.
        """
        self.module.log(msg="EasyRsa::validate__sign()")

        crt_file = os.path.join(self.pki_dir, "issued", f"{self.req_cn_server}.crt")

        if os.path.exists(crt_file):
            return True
        else:
            return False

    # ----------------------------------------------------------------------------------------------

    def _exec(self, commands: Sequence[str], check_rc: bool = False) -> ExecResult:
        """
        Execute a command via the underlying Ansible module.

        Args:
            commands: Command and arguments as a sequence of strings.
            check_rc: Passed through to ``module.run_command``; when True, the
                module may raise/fail on non-zero return codes depending on its behavior.

        Returns:
            tuple[int, str, str]: (rc, stdout, stderr)
                rc: Process return code.
                stdout: Captured standard output.
                stderr: Captured standard error.
        """
        self.module.log(msg=f"_exec(commands={commands}, check_rc={check_rc}")

        rc, out, err = self.module.run_command(commands, check_rc=check_rc)

        if int(rc) != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err

    def result_values(self, out: str, err: str) -> List[str]:
        """
        Merge stdout and stderr into a single list of output lines.

        Args:
            out: Raw stdout string.
            err: Raw stderr string.

        Returns:
            list[str]: Concatenated list of lines (stdout lines first, then stderr lines).
        """
        _out = out.splitlines()
        _err = err.splitlines()
        _output: List[str] = []
        _output += _out
        _output += _err
        # self.module.log(msg=f"= output: {_output}")
        return _output
