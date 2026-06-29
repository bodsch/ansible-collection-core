#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import re
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
module: yay
version_added: "2.14.0"
author: "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Install, upgrade or remove Arch Linux packages with the yay AUR helper

description:
  - Manage packages on Arch Linux using the C(yay) AUR helper.
  - C(yay) wraps C(pacman) and transparently builds and installs packages from the
    Arch User Repository (AUR) as well as the regular repositories.
  - Multiple packages can be managed in a single task.
  - Idempotency is determined without making changes first - C(pacman --query) is used
    to detect already installed packages and C(yay --query --upgrades) to detect
    available updates. Only packages that actually need an action are passed to C(yay).
  - Package removal is performed with C(yay --remove).

options:
  state:
    description:
      - Define the desired package state.
      - C(present) installs packages that are not installed yet and leaves already
        installed packages untouched.
      - C(latest) installs missing packages and upgrades installed packages for which
        an update is available.
      - C(absent) removes installed packages.
    type: str
    choices:
      - present
      - latest
      - absent
    default: present

  name:
    description:
      - List of package names to manage.
      - A single package name may be given as a string and is treated as a one element list.
    type: list
    elements: str
    required: true
    aliases:
      - pkg
      - package

  extra_args:
    description:
      - Additional arguments passed to C(yay) during installation.
      - Useful for flags such as C(--mflags) or C(--answerdiff).
    type: list
    elements: str
    required: false

notes:
  - This module does not support check mode.
  - C(yay) refuses to run as the C(root) user. The module is intended to run as a
    non-root build user, for example via C(become_user).
  - The build user must be allowed to install and remove packages, which C(yay)
    performs through C(sudo) internally.
  - The module never refreshes the sync databases on its own (no C(--refresh)), so
    no unintended partial system upgrades are triggered. AUR package versions are
    still resolved against the AUR by C(yay) itself.

requirements:
  - yay
  - pacman

attributes:
  check_mode:
    support: none
"""

EXAMPLES = r"""
- name: Install a single AUR package
  become: true
  become_user: aur_builder
  bodsch.core.yay:
    name: visual-studio-code-bin
    state: present

- name: Install multiple packages, skipping the ones already present
  become: true
  become_user: aur_builder
  bodsch.core.yay:
    name:
      - visual-studio-code-bin
      - google-chrome
      - spotify
    state: present

- name: Install and keep packages up to date
  become: true
  become_user: aur_builder
  bodsch.core.yay:
    name:
      - yay
      - paru
    state: latest

- name: Install a package with additional yay flags
  become: true
  become_user: aur_builder
  bodsch.core.yay:
    name: php-pear
    state: present
    extra_args:
      - --cleanafter
      - --removemake

- name: Remove packages
  become: true
  become_user: aur_builder
  bodsch.core.yay:
    name:
      - spotify
    state: absent
"""

RETURN = r"""
changed:
  description:
    - Indicates whether the module changed the target system.
    - Returned as C(true) when at least one package was installed, upgraded or removed.
  returned: always
  type: bool
  sample: false

failed:
  description:
    - Indicates whether the module execution failed.
  returned: always
  type: bool
  sample: false

msg:
  description:
    - Human-readable result message.
  returned: always
  type: str
  sample: All requested packages are already installed.

packages:
  description:
    - List of packages that were installed, upgraded or removed during this run.
    - Empty when the requested state was already satisfied.
  returned: always
  type: list
  elements: str
  sample:
    - visual-studio-code-bin
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


# "pacman --query" prints one "<name> <version>" pair per line.
_PACMAN_Q_RE = re.compile(r"^(?P<name>\S+)\s+(?P<ver>\S+)\s*$")
# "yay --query --upgrades" prints "<name> <oldver> -> <newver>" per upgradable package.
_YAY_QU_RE = re.compile(r"^(?P<name>\S+)\s+\S+\s+->\s+\S+")


class Yay:
    """
    Manage Arch Linux packages with the yay AUR helper.

    Notes:
      - yay refuses to run as root; the module is expected to run as a non-root build
        user that is allowed to install/remove packages (yay escalates via sudo).
    """

    def __init__(self, module: AnsibleModuleLike):
        """
        Initialize helper state from Ansible module parameters.
        """
        self.module: AnsibleModuleLike = module
        self.module.log("Yay::__init__()")

        self.state: str = module.params.get("state")
        self.names: List[str] = module.params.get("name") or []
        self.extra_args: Optional[List[str]] = module.params.get("extra_args")

        self.yay_binary: Optional[str] = self.module.get_bin_path("yay", True)
        self.pacman_binary: Optional[str] = self.module.get_bin_path("pacman", True)

    def run(self) -> Dict[str, Any]:
        """
        Execute the requested state transition.

        Returns:
          A result dictionary consumable by Ansible's exit_json().
        """
        self.module.log(f"Yay::run() - state: {self.state}, names: {self.names}")

        if self.state == "absent":
            return self._remove()

        # present / latest both install missing packages; latest additionally upgrades.
        return self._install(upgrade=self.state == "latest")

    def _install(self, upgrade: bool) -> Dict[str, Any]:
        """
        Install missing packages and, when ``upgrade`` is set, also upgrade outdated ones.

        Args:
          upgrade: If True, packages with an available update are included.

        Returns:
          Result dictionary for exit_json().
        """
        self.module.log(f"Yay::_install(upgrade: {upgrade})")

        installed = self._query_installed(self.names)
        missing = [name for name in self.names if name not in installed]

        # Preserve the order given by the user and avoid duplicates.
        to_install: List[str] = list(missing)

        if upgrade:
            already_installed = [name for name in self.names if name in installed]
            upgradable = self._query_upgradable(already_installed)
            for name in self.names:
                if name in upgradable and name not in to_install:
                    to_install.append(name)

        if not to_install:
            msg = (
                "All requested packages are already installed and up to date."
                if upgrade
                else "All requested packages are already installed."
            )
            return dict(changed=False, failed=False, msg=msg, packages=[])

        rc, _out, err = self._yay_install(to_install)

        if rc == 0:
            verb = "installed or upgraded" if upgrade else "installed"
            return dict(
                changed=True,
                failed=False,
                msg=f"Packages {verb}: {', '.join(to_install)}.",
                packages=to_install,
            )

        return dict(
            failed=True,
            changed=False,
            msg=f"An error occurred while installing packages: {err}",
            packages=[],
        )

    def _remove(self) -> Dict[str, Any]:
        """
        Remove the requested packages that are currently installed.

        Returns:
          Result dictionary for exit_json().
        """
        self.module.log("Yay::_remove()")

        installed = self._query_installed(self.names)
        to_remove = [name for name in self.names if name in installed]

        if not to_remove:
            return dict(
                changed=False,
                failed=False,
                msg="None of the requested packages are installed.",
                packages=[],
            )

        args: List[str] = [
            self.yay_binary or "yay",
            "--remove",
            "--cascade",
            "--recursive",
            "--noconfirm",
        ] + to_remove

        rc, _out, err = self._exec(args, check=False)

        if rc == 0:
            return dict(
                changed=True,
                failed=False,
                msg=f"Packages removed: {', '.join(to_remove)}.",
                packages=to_remove,
            )

        return dict(
            failed=True,
            changed=False,
            msg=f"An error occurred while removing packages: {err}",
            packages=[],
        )

    def _yay_install(self, packages: Sequence[str]) -> Tuple[int, str, str]:
        """
        Build and install the given packages with yay.

        The sync databases are intentionally not refreshed (no ``--refresh``) to avoid
        triggering an unintended partial system upgrade.

        Returns:
          Tuple (rc, out, err).
        """
        self.module.log(f"Yay::_yay_install(packages: {packages})")

        args: List[str] = [
            self.yay_binary or "yay",
            "--sync",
            "--noconfirm",
            "--needed",
        ] + list(packages)

        if self.extra_args:
            args += self.extra_args

        return self._exec(args, check=False)

    def _query_installed(self, names: Sequence[str]) -> Set[str]:
        """
        Return the subset of ``names`` that pacman reports as installed.

        A single "pacman --query <names...>" call prints the installed packages to
        stdout and reports missing ones via a non-zero return code; the latter is
        expected and not treated as an error.
        """
        self.module.log(f"Yay::_query_installed(names: {names})")

        if not names:
            return set()

        args: List[str] = [self.pacman_binary or "pacman", "--query"] + list(names)
        _rc, out, _err = self._exec(args, check=False)

        installed: Set[str] = set()
        for line in out.splitlines():
            m = _PACMAN_Q_RE.match(line.strip())
            if m:
                installed.add(m.group("name"))

        return installed

    def _query_upgradable(self, names: Sequence[str]) -> Set[str]:
        """
        Return the subset of ``names`` for which yay reports an available update.

        "yay --query --upgrades" lists repository and AUR updates. It returns a
        non-zero code when nothing can be upgraded, which is expected here.
        """
        self.module.log(f"Yay::_query_upgradable(names: {names})")

        if not names:
            return set()

        args: List[str] = [self.yay_binary or "yay", "--query", "--upgrades"]
        _rc, out, _err = self._exec(args, check=False)

        wanted = set(names)
        upgradable: Set[str] = set()
        for line in out.splitlines():
            m = _YAY_QU_RE.match(line.strip())
            if m and m.group("name") in wanted:
                upgradable.add(m.group("name"))

        return upgradable

    def _exec(self, cmd: Sequence[str], check: bool = False) -> Tuple[int, str, str]:
        """
        Execute a command via Ansible's run_command().

        Args:
          cmd: Argument vector (already split).
          check: If True, fail the module on non-zero return code.

        Returns:
          Tuple (rc, out, err).
        """
        self.module.log(f"Yay::_exec(cmd: {cmd}, check: {check})")

        rc, out, err = self.module.run_command(list(cmd), check_rc=check)

        if rc != 0:
            self.module.log(f"  rc : '{rc}'")
            self.module.log(f"  out: '{out}'")
            self.module.log(f"  err: '{err}'")

        return (rc, out, err)


# ===========================================
# Module execution.
# ===========================================


def main() -> None:
    """
    Entrypoint for the Ansible module.
    """
    args = dict(
        state=dict(default="present", choices=["present", "latest", "absent"]),
        name=dict(
            type="list", elements="str", required=True, aliases=["pkg", "package"]
        ),
        extra_args=dict(type="list", elements="str", required=False),
    )
    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    yay = Yay(module)
    result = yay.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
