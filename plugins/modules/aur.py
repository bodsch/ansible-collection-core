#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import json
import os
import re
import tarfile
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url

__metaclass__ = type

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: aur
short_description: Install or remove Arch Linux packages from the AUR
version_added: "0.9.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Installs packages from the Arch User Repository (AUR) by building them with C(makepkg).
  - Recommended: install from a Git repository URL (cloned into C($HOME/<name>), then updated via C(git pull)).
  - Fallback: if C(repository) is omitted, the module queries the AUR RPC API and downloads/extracts the source tarball to build it.
  - Ensures idempotency by comparing the currently installed package version with the upstream version (prefers C(.SRCINFO),
  - falls back to parsing C(PKGBUILD)); pkgrel-only updates trigger a rebuild.

options:
  state:
    description:
      - Whether the package should be installed or removed.
    type: str
    default: present
    choices: [present, absent]

  name:
    description:
      - Package name to manage (pacman package name / AUR package name).
    type: str
    required: true

  repository:
    description:
      - Git repository URL that contains the PKGBUILD (usually under U(https://aur.archlinux.org)).
      - If omitted, the module uses the AUR RPC API to download the source tarball.
    type: str
    required: false

  extra_args:
    description:
      - Additional arguments passed to C(makepkg) (for example C(--skippgpcheck), C(--nocheck)).
    type: list
    elements: str
    required: false
    version_added: "2.2.4"

notes:
  - Check mode is not supported.
  - The module is expected to run as a non-root build user (e.g. via C(become_user: aur_builder)).
  - The build user must be able to install packages non-interactively (makepkg/pacman), and to remove
  - packages this module uses C(sudo pacman -R...) when C(state=absent).
  - Network access to AUR is required for repository cloning/pulling or tarball download.

requirements:
  - pacman
  - git (when C(repository) is used)
  - makepkg (base-devel)
  - sudo (for C(state=absent) removal path)
"""

EXAMPLES = r"""
- name: Install package via AUR repository (recommended)
  become: true
  become_user: aur_builder
  bodsch.core.aur:
    state: present
    name: icinga2
    repository: https://aur.archlinux.org/icinga2.git

- name: Install package via AUR repository with makepkg extra arguments
  become: true
  become_user: aur_builder
  bodsch.core.aur:
    state: present
    name: php-pear
    repository: https://aur.archlinux.org/php-pear.git
    extra_args:
      - --skippgpcheck

- name: Install package via AUR tarball download (repository omitted)
  become: true
  become_user: aur_builder
  bodsch.core.aur:
    state: present
    name: yay

- name: Remove package
  become: true
  bodsch.core.aur:
    state: absent
    name: yay
"""

RETURN = r"""
changed:
  description:
    - Whether the module made changes.
    - C(true) when a package was installed/rebuilt/removed, otherwise C(false).
  returned: always
  type: bool

failed:
  description:
    - Indicates whether the module failed.
  returned: always
  type: bool

msg:
  description:
    - Human readable status or error message.
    - For idempotent runs, typically reports that the version is already installed.
  returned: always
  type: str
  sample:
    - "Package yay successfully installed."
    - "Package yay successfully removed."
    - "Version 1.2.3-1 is already installed."
"""

# ---------------------------------------------------------------------------------------


class AnsibleModuleLike(Protocol):
    """Minimal typing surface for the Ansible module used by this helper."""

    params: Mapping[str, Any]

    def get_bin_path(self, arg: str, required: bool = False) -> Optional[str]:
        """
        Return the absolute path to an executable.

        Args:
            arg: Program name to look up in PATH.
            required: If True, the module typically fails when the binary is not found.

        Returns:
            Absolute path to the executable, or None if not found and not required.
        """
        ...

    def run_command(
        self, args: Sequence[str], check_rc: bool = True
    ) -> Tuple[int, str, str]:
        """
        Execute a command on the target host.

        Args:
            args: Argument vector (already split).
            check_rc: If True, non-zero return codes should be treated as errors.

        Returns:
            Tuple ``(rc, stdout, stderr)``.
        """
        ...

    def log(self, msg: str = "", **kwargs: Any) -> None:
        """
        Write a log/debug message via the Ansible module.

        Args:
            msg: Message text.
            **kwargs: Additional structured log fields (module dependent).
        """
        ...


_PACMAN_Q_RE = re.compile(r"^(?P<name>\S+)\s+(?P<ver>\S+)\s*$", re.MULTILINE)
_PKGBUILD_PKGVER_RE = re.compile(r"^pkgver=(?P<version>.*)\s*$", re.MULTILINE)
_PKGBUILD_EPOCH_RE = re.compile(r"^epoch=(?P<epoch>.*)\s*$", re.MULTILINE)
_SRCINFO_PKGVER_RE = re.compile(r"^\s*pkgver\s*=\s*(?P<version>.*)\s*$", re.MULTILINE)
_SRCINFO_EPOCH_RE = re.compile(r"^\s*epoch\s*=\s*(?P<epoch>.*)\s*$", re.MULTILINE)
_PKGBUILD_PKGREL_RE = re.compile(r"^pkgrel=(?P<pkgrel>.*)\s*$", re.MULTILINE)
_SRCINFO_PKGREL_RE = re.compile(r"^\s*pkgrel\s*=\s*(?P<pkgrel>.*)\s*$", re.MULTILINE)


class Aur:
    """
    Implements AUR package installation/removal.

    Notes:
      - The module is expected to run as a non-root user that is allowed to build packages
        via makepkg (e.g. a dedicated 'aur_builder' user).
      - Repository-based installation is recommended. The tarball-based installation path
        exists as a fallback when no repository URL is provided.
    """

    module = None

    def __init__(self, module: AnsibleModuleLike):
        """
        Initialize helper state from Ansible module parameters.
        """
        self.module = module
        self.module.log("Aur::__init__()")

        self.state: str = module.params.get("state")
        self.name: str = module.params.get("name")
        self.repository: Optional[str] = module.params.get("repository")
        self.extra_args: Optional[List[str]] = module.params.get("extra_args")

        # Cached state for idempotency decisions during this module run.
        self._installed_version: Optional[str] = None
        self._installed_version_full: Optional[str] = None

        self.pacman_binary: Optional[str] = self.module.get_bin_path("pacman", True)
        self.git_binary: Optional[str] = self.module.get_bin_path("git", True)

    def run(self) -> Dict[str, Any]:
        """
        Execute the requested state transition.

        Returns:
          A result dictionary consumable by Ansible's exit_json().
        """
        self.module.log("Aur::run()")

        installed, installed_version = self.package_installed(self.name)

        # Store installed version for use by other code paths (e.g. AUR tarball installs).
        self._installed_version = installed_version
        self._installed_version_full = (
            self._package_installed_full_version(self.name) if installed else None
        )

        if self._installed_version_full:
            self.module.log(
                msg=f"  {self.name} full version: {self._installed_version_full}"
            )

        self.module.log(
            msg=f"  {self.name} is installed: {installed} / version: {installed_version}"
        )

        if installed and self.state == "absent":
            sudo_binary = self.module.get_bin_path("sudo", True)

            args: List[str] = [
                sudo_binary,
                self.pacman_binary or "pacman",
                "--remove",
                "--cascade",
                "--recursive",
                "--noconfirm",
                self.name,
            ]

            rc, _, err = self._exec(args)

            if rc == 0:
                return dict(
                    changed=True, msg=f"Package {self.name} successfully removed."
                )
            return dict(
                failed=True,
                changed=False,
                msg=f"An error occurred while removing the package {self.name}: {err}",
            )

        if self.state == "present":
            if self.repository:
                rc, out, err, changed = self.install_from_repository(installed_version)

                if rc == 99:
                    msg = out
                    rc = 0
                else:
                    msg = f"Package {self.name} successfully installed."
            else:
                rc, out, err, changed = self.install_from_aur()
                msg = (
                    out
                    if rc == 0 and out
                    else f"Package {self.name} successfully installed."
                )

            if rc == 0:
                return dict(failed=False, changed=changed, msg=msg)
            return dict(failed=True, msg=err)

        return dict(
            failed=False,
            changed=False,
            msg="It's all right. Keep moving! There is nothing to see!",
        )

    def package_installed(self, package: str) -> Tuple[bool, Optional[str]]:
        """
        Determine whether a package is installed and return its version key (epoch+pkgver, without pkgrel).

        Args:
          package: Pacman package name to check.

        Returns:
          Tuple (installed, version_string)
            - installed: True if pacman reports the package is installed.
            - version_string: comparable version key '<epoch>:<pkgver>' without pkgrel (epoch optional) or None if not installed.
        """
        self.module.log(f"Aur::package_installed(package: {package})")

        args: List[str] = [
            self.pacman_binary or "pacman",
            "--query",
            package,
        ]

        rc, out, _ = self._exec(args, check=False)

        version_string: Optional[str] = None
        if out:
            m = _PACMAN_Q_RE.search(out)
            if m and m.group("name") == package:
                full_version = m.group("ver")
                # pacman prints "<epoch>:<pkgver>-<pkgrel>" (epoch optional).
                version_string = (
                    full_version.rsplit("-", 1)[0]
                    if "-" in full_version
                    else full_version
                )

        return (rc == 0, version_string)

    def _package_installed_full_version(self, package: str) -> Optional[str]:
        """
        Return the full pacman version string for an installed package.

        The returned string includes both epoch and pkgrel if present, matching the output
        format of "pacman -Q":
          - "<epoch>:<pkgver>-<pkgrel>" (epoch optional)

        Args:
          package: Pacman package name to check.

        Returns:
          The full version string or None if the package is not installed.
        """
        self.module.log(f"Aur::_package_installed_full_version(package: {package})")

        args: List[str] = [
            self.pacman_binary or "pacman",
            "--query",
            package,
        ]

        rc, out, _ = self._exec(args, check=False)
        if rc != 0 or not out:
            return None

        m = _PACMAN_Q_RE.search(out)
        if m and m.group("name") == package:
            return m.group("ver")

        return None

    def run_makepkg(self, directory: str) -> Tuple[int, str, str]:
        """
        Run makepkg to build and install a package.

        Args:
          directory: Directory containing the PKGBUILD.

        Returns:
          Tuple (rc, out, err) from the makepkg execution.
        """
        self.module.log(f"Aur::run_makepkg(directory: {directory})")
        self.module.log(f"  current dir : {os.getcwd()}")

        if not os.path.exists(directory):
            return (1, "", f"Directory '{directory}' does not exist.")

        makepkg_binary = self.module.get_bin_path("makepkg", required=True) or "makepkg"

        args: List[str] = [
            makepkg_binary,
            "--syncdeps",
            "--install",
            "--noconfirm",
            "--needed",
            "--clean",
        ]

        if self.extra_args:
            args += self.extra_args

        with self._pushd(directory):
            rc, out, err = self._exec(args, check=False)

        return (rc, out, err)

    def install_from_aur(self) -> Tuple[int, str, str, bool]:
        """
        Install a package by downloading its source tarball from AUR.

        Returns:
          Tuple (rc, out, err, changed)
        """
        self.module.log("Aur::install_from_aur()")

        import tempfile

        try:
            rpc = self._aur_rpc_info(self.name)
        except Exception as exc:
            return (1, "", f"Failed to query AUR RPC API: {exc}", False)

        if rpc.get("resultcount") != 1:
            return (1, "", f"Package '{self.name}' not found on AUR.", False)

        result = rpc["results"][0]
        url_path = result.get("URLPath")
        if not url_path:
            return (1, "", f"AUR did not return a source URL for '{self.name}'.", False)

        tar_url = f"https://aur.archlinux.org/{url_path}"
        self.module.log(f"  tarball url {tar_url}")

        try:
            f = open_url(tar_url)
        except Exception as exc:
            return (1, "", f"Failed to download AUR tarball: {exc}", False)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with tarfile.open(mode="r|*", fileobj=f) as tar:
                    self._safe_extract_stream(tar, tmpdir)

                build_dir = self._find_pkgbuild_dir(tmpdir)
                if not build_dir:
                    return (
                        1,
                        "",
                        "Unable to locate PKGBUILD in extracted source tree.",
                        False,
                    )

                upstream_version = self._read_upstream_version_key(build_dir)
                upstream_full_version = self._read_upstream_full_version(build_dir)

                # Prefer comparing full versions (epoch:pkgver-pkgrel). This ensures pkgrel-only
                # bumps trigger a rebuild, matching pacman's notion of a distinct package version.
                if self._installed_version_full and upstream_full_version:
                    if self._installed_version_full == upstream_full_version:
                        return (
                            0,
                            f"Version {self._installed_version_full} is already installed.",
                            "",
                            False,
                        )
                elif self._installed_version and upstream_version:
                    if self._installed_version == upstream_version:
                        return (
                            0,
                            f"Version {self._installed_version} is already installed.",
                            "",
                            False,
                        )

                rc, out, err = self.run_makepkg(build_dir)
        except Exception as exc:
            return (1, "", f"Failed to extract/build AUR source: {exc}", False)

        return (rc, out, err, rc == 0)

    def install_from_repository(
        self, installed_version: Optional[str]
    ) -> Tuple[int, str, str, bool]:
        """
        Install a package from a Git repository (recommended).

        Args:
          installed_version: Currently installed version key '<epoch>:<pkgver>' without pkgrel (epoch optional) or None.

        Returns:
          Tuple (rc, out, err, changed)

        Special return code:
          - rc == 99 indicates "already installed / no change" (kept for backward compatibility).
        """
        self.module.log(
            f"Aur::install_from_repository(installed_version: {installed_version})"
        )

        base_dir = str(Path.home())
        repo_dir = os.path.join(base_dir, self.name)

        with self._pushd(base_dir):
            if not os.path.exists(repo_dir):
                rc, out, _err = self.git_clone(repository=self.repository or "")
                if rc != 0:
                    return (rc, out, "Unable to run 'git clone'.", False)

        with self._pushd(repo_dir):
            if os.path.exists(".git"):
                rc, out, _err = self.git_pull()
                if rc != 0:
                    return (rc, out, "Unable to run 'git pull'.", False)

        with self._pushd(repo_dir):
            pkgbuild_file = "PKGBUILD"
            if not os.path.exists(pkgbuild_file):
                return (1, "", "Unable to find PKGBUILD.", False)

            upstream_version = self._read_upstream_version_key(os.getcwd())
            upstream_full_version = self._read_upstream_full_version(os.getcwd())

            # Prefer comparing full versions (epoch:pkgver-pkgrel). This ensures pkgrel-only bumps
            # trigger a rebuild even if pkgver stayed constant.
            if self._installed_version_full and upstream_full_version:
                if self._installed_version_full == upstream_full_version:
                    return (
                        99,
                        f"Version {self._installed_version_full} is already installed.",
                        "",
                        False,
                    )
            elif installed_version and upstream_version:
                if installed_version == upstream_version:
                    return (
                        99,
                        f"Version {installed_version} is already installed.",
                        "",
                        False,
                    )

            self.module.log(
                msg=f"upstream version: {upstream_full_version or upstream_version}"
            )

            rc, out, err = self.run_makepkg(repo_dir)

        return (rc, out, err, rc == 0)

    def git_clone(self, repository: str) -> Tuple[int, str, str]:
        """
        Clone the repository into a local directory named after the package.

        Returns:
          Tuple (rc, out, err)
        """
        self.module.log(f"Aur::git_clone(repository: {repository})")

        if not self.git_binary:
            return (1, "", "git not found")

        args: List[str] = [
            self.git_binary,
            "clone",
            repository,
            self.name,
        ]

        rc, out, err = self._exec(args)
        return (rc, out, err)

    def git_pull(self) -> Tuple[int, str, str]:
        """
        Update an existing Git repository.

        Returns:
          Tuple (rc, out, err)
        """
        self.module.log("Aur::git_pull()")

        if not self.git_binary:
            return (1, "", "git not found")

        args: List[str] = [
            self.git_binary,
            "pull",
        ]

        rc, out, err = self._exec(args)
        return (rc, out, err)

    def _exec(self, cmd: Sequence[str], check: bool = False) -> Tuple[int, str, str]:
        """
        Execute a command via Ansible's run_command().

        Args:
          cmd: Argument vector (already split).
          check: If True, fail the module on non-zero return code.

        Returns:
          Tuple (rc, out, err)
        """
        self.module.log(f"Aur::_exec(cmd: {cmd}, check: {check})")

        rc, out, err = self.module.run_command(list(cmd), check_rc=check)

        if rc != 0:
            self.module.log(f"  rc : '{rc}'")
            self.module.log(f"  out: '{out}'")
            self.module.log(f"  err: '{err}'")

        return (rc, out, err)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @contextmanager
    def _pushd(self, directory: str) -> Iterator[None]:
        """
        Temporarily change the current working directory.

        This avoids leaking state across module runs and improves correctness of
        commands like makepkg, git clone, and git pull.
        """
        self.module.log(f"Aur::_pushd(directory: {directory})")

        prev = os.getcwd()
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(prev)

    def _aur_rpc_info(self, package: str) -> Dict[str, Any]:
        """
        Query the AUR RPC API for a package.

        Returns:
          Parsed JSON dictionary.
        """
        self.module.log(f"Aur::_aur_rpc_info(package: {package})")

        url = "https://aur.archlinux.org/rpc/?v=5&type=info&arg=" + urllib.parse.quote(
            package
        )
        self.module.log(f"  rpc url {url}")

        resp = open_url(url)
        return json.loads(resp.read().decode("utf-8"))

    def _safe_extract_stream(self, tar: tarfile.TarFile, target_dir: str) -> None:
        """
        Safely extract a tar stream into target_dir.

        This prevents path traversal attacks by validating each member's target path
        before extraction.
        """
        self.module.log(
            f"Aur::_safe_extract_stream(tar: {tar}, target_dir: {target_dir})"
        )

        target_real = os.path.realpath(target_dir)
        for member in tar:
            member_path = os.path.realpath(os.path.join(target_dir, member.name))
            if (
                not member_path.startswith(target_real + os.sep)
                and member_path != target_real
            ):
                raise ValueError(f"Blocked tar path traversal attempt: {member.name}")
            tar.extract(member, target_dir)

    def _find_pkgbuild_dir(self, root_dir: str) -> Optional[str]:
        """
        Locate the directory that contains the PKGBUILD file inside root_dir.
        """
        self.module.log(f"Aur::_find_pkgbuild_dir(root_dir: {root_dir})")

        for dirpath, _, filenames in os.walk(root_dir):
            if "PKGBUILD" in filenames:
                return dirpath
        return None

    def _read_pkgbuild_pkgver(self, pkgbuild_path: str) -> str:
        """
        Read pkgver from a PKGBUILD file.

        Note:
          This is a best-effort parse of 'pkgver='. It does not execute PKGBUILD code.
        """
        self.module.log(f"Aur::_read_pkgbuild_pkgver(pkgbuild_path: {pkgbuild_path})")

        try:
            with open(pkgbuild_path, "r", encoding="utf-8") as f:
                data = f.read()
        except OSError as exc:
            self.module.log(msg=f"Unable to read PKGBUILD: {exc}")
            return ""

        m = _PKGBUILD_PKGVER_RE.search(data)
        return self._sanitize_scalar(m.group("version")) if m else ""

    def _read_pkgbuild_pkgrel(self, pkgbuild_path: str) -> str:
        """
        Read pkgrel from a PKGBUILD file.

        Note:
          This is a best-effort parse of 'pkgrel='. It does not execute PKGBUILD code.
        """
        self.module.log(f"Aur::_read_pkgbuild_pkgrel(pkgbuild_path: {pkgbuild_path})")

        try:
            with open(pkgbuild_path, "r", encoding="utf-8") as f:
                data = f.read()
        except OSError as exc:
            self.module.log(msg=f"Unable to read PKGBUILD: {exc}")
            return ""

        m = _PKGBUILD_PKGREL_RE.search(data)
        return self._sanitize_scalar(m.group("pkgrel")) if m else ""

    def _read_pkgbuild_full_version(self, pkgbuild_path: str) -> str:
        """
        Read epoch/pkgver/pkgrel from PKGBUILD and return a comparable full version string.

        The returned format matches pacman's version string without architecture:
          - "<epoch>:<pkgver>-<pkgrel>" (epoch optional)
        """
        self.module.log(
            f"Aur::_read_pkgbuild_full_version(pkgbuild_path: {pkgbuild_path})"
        )

        pkgver = self._read_pkgbuild_pkgver(pkgbuild_path)
        pkgrel = self._read_pkgbuild_pkgrel(pkgbuild_path)
        epoch = self._read_pkgbuild_epoch(pkgbuild_path)

        return self._make_full_version(pkgver=pkgver, pkgrel=pkgrel, epoch=epoch)

    def _read_srcinfo_full_version(self, srcinfo_path: str) -> str:
        """
        Read epoch/pkgver/pkgrel from a .SRCINFO file.
        """
        self.module.log(
            f"Aur::_read_srcinfo_full_version(srcinfo_path: {srcinfo_path})"
        )

        try:
            with open(srcinfo_path, "r", encoding="utf-8") as f:
                data = f.read()
        except OSError:
            return ""

        pkgver_m = _SRCINFO_PKGVER_RE.search(data)
        pkgrel_m = _SRCINFO_PKGREL_RE.search(data)
        epoch_m = _SRCINFO_EPOCH_RE.search(data)

        pkgver = self._sanitize_scalar(pkgver_m.group("version")) if pkgver_m else ""
        pkgrel = self._sanitize_scalar(pkgrel_m.group("pkgrel")) if pkgrel_m else ""
        epoch = self._sanitize_scalar(epoch_m.group("epoch")) if epoch_m else None

        return self._make_full_version(pkgver=pkgver, pkgrel=pkgrel, epoch=epoch)

    def _read_upstream_full_version(self, directory: str) -> str:
        """
        Determine the upstream full version for idempotency decisions.

        The function prefers .SRCINFO (static metadata) and falls back to PKGBUILD parsing.
        If pkgrel cannot be determined, the function may return an epoch/pkgver-only key.
        """
        self.module.log(f"Aur::_read_upstream_full_version(directory: {directory})")

        srcinfo_path = os.path.join(directory, ".SRCINFO")
        if os.path.exists(srcinfo_path):
            v = self._read_srcinfo_full_version(srcinfo_path)
            if v:
                return v

        pkgbuild_path = os.path.join(directory, "PKGBUILD")
        if os.path.exists(pkgbuild_path):
            v = self._read_pkgbuild_full_version(pkgbuild_path)
            if v:
                return v

        return ""

    def _read_pkgbuild_version_key(self, pkgbuild_path: str) -> str:
        """
        Read epoch/pkgver from PKGBUILD and return a comparable version key.
        """
        self.module.log(
            f"Aur::_read_pkgbuild_version_key(pkgbuild_path: {pkgbuild_path})"
        )

        pkgver = self._read_pkgbuild_pkgver(pkgbuild_path)
        epoch = self._read_pkgbuild_epoch(pkgbuild_path)

        return self._make_version_key(pkgver=pkgver, epoch=epoch)

    def _read_srcinfo_version_key(self, srcinfo_path: str) -> str:
        """
        Read epoch/pkgver from a .SRCINFO file.
        """
        self.module.log(f"Aur::_read_srcinfo_version_key(srcinfo_path: {srcinfo_path})")

        try:
            with open(srcinfo_path, "r", encoding="utf-8") as f:
                data = f.read()
        except OSError:
            return ""

        pkgver_m = _SRCINFO_PKGVER_RE.search(data)
        epoch_m = _SRCINFO_EPOCH_RE.search(data)

        pkgver = self._sanitize_scalar(pkgver_m.group("version")) if pkgver_m else ""
        epoch = self._sanitize_scalar(epoch_m.group("epoch")) if epoch_m else None

        return self._make_version_key(pkgver=pkgver, epoch=epoch)

    def _read_pkgbuild_epoch(self, pkgbuild_path: str) -> Optional[str]:
        """
        Read epoch from a PKGBUILD file.
        """
        self.module.log(f"Aur::_read_pkgbuild_epoch(pkgbuild_path: {pkgbuild_path})")

        try:
            with open(pkgbuild_path, "r", encoding="utf-8") as f:
                data = f.read()
        except OSError as exc:
            self.module.log(msg=f"Unable to read PKGBUILD: {exc}")
            return None

        m = _PKGBUILD_EPOCH_RE.search(data)

        return self._sanitize_scalar(m.group("epoch")) if m else None

    def _read_upstream_version_key(self, directory: str) -> str:
        """
        Determine the upstream package version key for idempotency decisions.

        The function prefers .SRCINFO (static metadata) and falls back to PKGBUILD
        parsing if .SRCINFO is missing.
        """
        self.module.log(f"Aur::_read_upstream_version_key(directory: {directory})")

        srcinfo_path = os.path.join(directory, ".SRCINFO")
        if os.path.exists(srcinfo_path):
            v = self._read_srcinfo_version_key(srcinfo_path)
            if v:
                return v

        pkgbuild_path = os.path.join(directory, "PKGBUILD")
        if os.path.exists(pkgbuild_path):
            return self._read_pkgbuild_version_key(pkgbuild_path)

        return ""

    def _sanitize_scalar(self, value: str) -> str:
        """
        Sanitize a scalar value extracted from PKGBUILD/.SRCINFO.

        This removes surrounding quotes and trims whitespace. It is intentionally conservative
        and does not attempt to evaluate shell expansions or PKGBUILD functions.
        """
        self.module.log(f"Aur::_sanitize_scalar(value: {value})")

        v = value.strip()
        if (v.startswith('"') and v.endswith('"')) or (
            v.startswith("'") and v.endswith("'")
        ):
            v = v[1:-1].strip()

        return v

    def _make_version_key(self, pkgver: str, epoch: Optional[str]) -> str:
        """
        Build a comparable version key.

        Pacman formats versions as: '<epoch>:<pkgver>-<pkgrel>' (epoch optional).
        This module compares '<epoch>:<pkgver>' (without pkgrel).
        """
        self.module.log(f"Aur::_make_version_key(pkgver: {pkgver}, epoch: {epoch})")

        pv = pkgver.strip()
        ep = self._sanitize_scalar(epoch) if epoch is not None else ""
        if ep and ep != "0":
            return f"{ep}:{pv}" if pv else f"{ep}:"

        return pv

    def _make_full_version(self, pkgver: str, pkgrel: str, epoch: Optional[str]) -> str:
        """
        Build a comparable full version string.

        The returned format matches pacman's version string:
          - "<epoch>:<pkgver>-<pkgrel>" (epoch optional)

        If pkgrel is empty, the function falls back to an epoch/pkgver-only key.
        """
        self.module.log(
            f"Aur::_make_full_version(pkgver: {pkgver}, pkgrel: {pkgrel}, epoch: {epoch})"
        )

        pv = pkgver.strip()
        pr = pkgrel.strip()
        ep = self._sanitize_scalar(epoch) if epoch is not None else ""

        base = f"{ep}:{pv}" if ep and ep != "0" else pv
        if not pr:
            return base

        return f"{base}-{pr}" if base else ""


# ===========================================
# Module execution.
# ===========================================


def main() -> None:
    """
    Entrypoint for the Ansible module.
    """
    args = dict(
        state=dict(default="present", choices=["present", "absent"]),
        repository=dict(type="str", required=False),
        name=dict(type="str", required=True),
        extra_args=dict(type="list", required=False),
    )
    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    aur = Aur(module)
    result = aur.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
