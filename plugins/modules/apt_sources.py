#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.deb822_repo import (
    Deb822RepoManager,
    Deb822RepoSpec,
)

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
module: apt_sources
version_added: '2.9.0'
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Manage APT deb822 (.sources) repositories with repo-specific keyrings.
description:
  - Creates/removes deb822 formatted APT repository files in /etc/apt/sources.list.d.
  - Supports importing repo-specific signing keys either via downloading a key file (with optional dearmor/validation)
    or by installing a keyring .deb package (e.g. Sury keyring).
  - Optionally runs apt-get update when changes occur.
options:
  name:
    description: Logical name of the repository (used for defaults like filename).
    type: str
    required: true
  state:
    description: Whether the repository should be present or absent.
    type: str
    choices: [present, absent]
    default: present
  dest:
    description: Full path of the .sources file. If omitted, computed from filename/name.
    type: str
  filename:
    description: Filename under /etc/apt/sources.list.d/ (must end with .sources).
    type: str
  types:
    description: Repository types (deb, deb-src).
    type: list
    elements: str
    default: ["deb"]
  uris:
    description: Base URIs of the repository.
    type: list
    elements: str
    required: true
  suites:
    description: Suites / distributions (e.g. bookworm). If suite ends with '/', Components must be omitted.
    type: list
    elements: str
    required: true
  components:
    description: Components (e.g. main, contrib). Required unless suite is a path ending in '/'.
    type: list
    elements: str
    default: []
  architectures:
    description: Restrict repository to architectures (e.g. amd64).
    type: list
    elements: str
    default: []
  enabled:
    description: Whether the source is enabled (Enabled: yes/no).
    type: bool
    default: true
  signed_by:
    description: Absolute path to a keyring file used as Signed-By. If omitted and key.method is download/deb, derived from key config.
    type: str
  key:
    description: Key import configuration.
    type: dict
    suboptions:
      method:
        description: How to manage keys.
        type: str
        choices: [none, download, deb]
        default: none
      url:
        description: URL to download the key (download) or keyring .deb (deb).
        type: str
      dest:
        description: Destination keyring path for method=download.
        type: str
      checksum:
        description: Optional SHA256 checksum of downloaded content (raw download). Enables strict idempotence and integrity checks.
        type: str
      dearmor:
        description: If true and downloaded key is ASCII armored, dearmor via gpg to a binary keyring.
        type: bool
        default: true
      validate:
        description: If true, validate the final key file via gpg --show-keys.
        type: bool
        default: true
      mode:
        description: File mode for key files / deb cache files.
        type: str
        default: "0644"
      deb_cache_path:
        description: Destination path for downloaded .deb when method=deb.
        type: str
      deb_keyring_path:
        description: Explicit keyring path provided by that .deb (if auto-detection is not possible).
        type: str
  update_cache:
    description: Run apt-get update if repo/key changed.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Add Sury repo via keyring deb package (Debian)
  deb822_repo:
    name: debsuryorg
    uris: ["https://packages.sury.org/php/"]
    suites: ["{{ ansible_facts.distribution_release }}"]
    components: ["main"]
    key:
      method: deb
      url: "https://packages.sury.org/debsuryorg-archive-keyring.deb"
      deb_cache_path: "/var/cache/apt/debsuryorg-archive-keyring.deb"
      # optional if auto-detect fails:
      # deb_keyring_path: "/usr/share/keyrings/debsuryorg-archive-keyring.gpg"
    update_cache: true
  become: true

- name: Add CZ.NIC repo via key download (bookworm)
  deb822_repo:
    name: cznic-labs-knot-resolver
    uris: ["https://pkg.labs.nic.cz/knot-resolver"]
    suites: ["bookworm"]
    components: ["main"]
    key:
      method: download
      url: "https://pkg.labs.nic.cz/gpg"
      dest: "/usr/share/keyrings/cznic-labs-pkg.gpg"
      dearmor: true
      validate: true
    update_cache: true
  become: true
"""

RETURN = r"""
repo_path:
  description: Path to the managed .sources file.
  returned: always
  type: str
key_path:
  description: Path to the keyring file used as Signed-By (if managed/derived).
  returned: when key method used or signed_by provided
  type: str
changed:
  description: Whether any change was made.
  returned: always
  type: bool
messages:
  description: Informational messages about performed actions.
  returned: always
  type: list
  elements: str
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


class AptSources:
    """
    Manage APT deb822 (.sources) repositories with repo-specific keyrings.

    This class is the orchestration layer used by the module entrypoint. It delegates the
    actual file/key handling to :class:`Deb822RepoManager` and is responsible for:
      - computing the target .sources path
      - ensuring/removing repository key material (method=download or method=deb)
      - ensuring/removing the repository file
      - optionally running ``apt-get update`` when changes occur
    """

    module = None

    def __init__(self, module: AnsibleModuleLike):
        """
        Initialize the handler and snapshot module parameters.

        Args:
            module: An AnsibleModule-like object providing ``params``, logging and command execution.
        """
        self.module = module

        self.module.log("AptSources::__init__()")

        self.name = module.params.get("name")
        self.state = module.params.get("state")
        self.destination = module.params.get("dest")
        self.filename = module.params.get("filename")
        self.types = module.params.get("types")
        self.uris = module.params.get("uris")
        self.suites = module.params.get("suites")
        self.components = module.params.get("components")
        self.architectures = module.params.get("architectures")
        self.enabled = module.params.get("enabled")
        self.update_cache = module.params.get("update_cache")
        self.signed_by = module.params.get("signed_by")
        self.keys = module.params.get("key")

        self.option_method = self.keys.get("method")
        self.option_url = self.keys.get("url")
        self.option_dest = self.keys.get("dest")
        self.option_checksum = self.keys.get("checksum")
        self.option_dearmor = self.keys.get("dearmor")
        self.option_validate = self.keys.get("validate")
        self.option_mode = self.keys.get("mode")
        self.option_deb_cache_path = self.keys.get("deb_cache_path")
        self.option_deb_keyring_path = self.keys.get("deb_keyring_path")

    def run(self) -> Dict[str, Any]:
        """
        Apply the requested repository state.

        For ``state=present`` the method ensures the signing key (if configured) and then writes the
        deb822 repository file. For ``state=absent`` it removes the repository file and any managed
        key material.

        Returns:
            A result dictionary intended for ``module.exit_json()``, containing:

            - ``changed``: Whether any managed resource changed.
            - ``repo_path``: Path to the managed ``.sources`` file.
            - ``key_path``: Path to the keyring file used for ``Signed-By`` (if any).
            - ``messages``: Informational messages describing performed actions.

        Note:
            When ``state=absent`` this method exits the module early via ``module.exit_json()``.
        """
        mng = Deb822RepoManager(self.module)

        repo_path = self._ensure_sources_path(
            mng, self.name, self.destination, self.filename
        )

        changed = False
        messages: List[str] = []

        if self.state == "absent":
            key_cfg: Dict[str, Any] = self.keys or {"method": "none"}

            if mng.remove_file(path=repo_path, check_mode=bool(self.module.check_mode)):
                changed = True
                messages.append(f"removed repo file: {repo_path}")

            # remove managed key material as well
            key_res = mng.remove_key(
                key_cfg=key_cfg,
                signed_by=self.signed_by,
                check_mode=bool(self.module.check_mode),
            )
            if key_res.messages:
                messages.extend(list(key_res.messages))
            if key_res.changed:
                changed = True

            self.module.exit_json(
                changed=changed,
                repo_path=repo_path,
                key_path=(self.signed_by or key_res.key_path),
                messages=messages,
            )

        # present
        key_cfg: Dict[str, Any] = self.keys or {"method": "none"}
        key_res = mng.ensure_key(key_cfg=key_cfg, check_mode=self.module.check_mode)
        if key_res.messages:
            messages.extend(list(key_res.messages))
        if key_res.changed:
            changed = True

        signed_by: Optional[str] = self.signed_by or key_res.key_path

        spec = Deb822RepoSpec(
            types=self.types,
            uris=self.uris,
            suites=self.suites,
            components=self.components,
            architectures=self.architectures,
            enabled=self.enabled,
            signed_by=signed_by,
        )

        repo_mode = 0o644
        repo_res = mng.ensure_repo_file(
            repo_path=repo_path,
            spec=spec,
            mode=repo_mode,
            check_mode=self.module.check_mode,
        )
        if repo_res.changed:
            changed = True
            messages.append(f"updated repo file: {repo_path}")

        # Optionally update cache only if something changed
        if self.update_cache and (key_res.changed or repo_res.changed):
            _, out = mng.apt_update(check_mode=self.module.check_mode)
            messages.append("apt-get update executed")
            if out:
                # keep it short to avoid noisy output
                messages.append("apt-get update: ok")

        return dict(
            changed=changed,
            repo_path=repo_path,
            key_path=signed_by,
            messages=messages,
        )

    def _ensure_sources_path(
        self,
        manager: Deb822RepoManager,
        name: str,
        dest: Optional[str],
        filename: Optional[str],
    ) -> str:
        """
        Determine the destination path of the ``.sources`` file.

        If ``dest`` is provided it is returned unchanged. Otherwise a filename is derived from
        ``filename`` or ``name``, validated, and placed under ``/etc/apt/sources.list.d/``.

        Args:
            manager: Repo manager used for validation.
            name: Logical repository name.
            dest: Explicit destination path (optional).
            filename: Filename (optional, must end in ``.sources``).

        Returns:
            The absolute path of the repository file to manage.
        """

        if dest:
            return dest

        fn = filename or f"{name}.sources"
        # validate filename rules and suffix
        manager.validate_filename(fn)
        return f"/etc/apt/sources.list.d/{fn}"


def main() -> None:
    """
    Entrypoint for the Ansible module.

    Parses module arguments, executes the handler and returns the result via ``exit_json``.
    """
    args = dict(
        name=dict(type="str", required=True),
        state=dict(type="str", choices=["present", "absent"], default="present"),
        dest=dict(type="str", required=False),
        filename=dict(type="str", required=False),
        types=dict(type="list", elements="str", default=["deb"]),
        uris=dict(type="list", elements="str", required=True),
        suites=dict(type="list", elements="str", required=True),
        components=dict(type="list", elements="str", default=[]),
        architectures=dict(type="list", elements="str", default=[]),
        enabled=dict(type="bool", default=True),
        signed_by=dict(type="str", required=False),
        key=dict(
            type="dict",
            required=False,
            options=dict(
                method=dict(
                    type="str", choices=["none", "download", "deb"], default="none"
                ),
                url=dict(type="str", required=False),
                dest=dict(type="str", required=False),
                checksum=dict(type="str", required=False),
                dearmor=dict(type="bool", default=True),
                validate=dict(type="bool", default=True),
                mode=dict(type="str", default="0644"),
                deb_cache_path=dict(type="str", required=False),
                deb_keyring_path=dict(type="str", required=False),
            ),
        ),
        update_cache=dict(type="bool", default=False),
    )
    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    handler = AptSources(module)
    result = handler.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
