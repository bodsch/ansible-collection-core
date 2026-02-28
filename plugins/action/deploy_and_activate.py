"""
deploy_and_activate.py (action plugin)

Controller-side orchestration for deploying versioned binaries and activating them via symlinks.

This action plugin wraps a remote worker module (bodsch.core.deploy_and_activate_remote)
and provides two operational modes:

1) remote_src=False (controller-local source):
   - Validate that extracted binaries exist on the Ansible controller in src_dir.
   - Stage these files onto the remote host via ActionBase._transfer_file().
   - Invoke the remote worker module to copy into install_dir and enforce perms/caps/symlinks.

2) remote_src=True (remote-local source):
   - Assume binaries already exist on the remote host in src_dir.
   - Invoke the remote worker module to copy into install_dir and enforce perms/caps/symlinks.

Implementation note:
- Do not call ansible.builtin.copy via _execute_module() to transfer controller-local files.
  That bypasses the copy action logic and will not perform controller->remote transfer reliably.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    cast,
)

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display

display = Display()

REMOTE_WORKER_MODULE = "bodsch.core.deploy_and_activate_remote"

DOCUMENTATION = r"""
---
module: deploy_and_activate
short_description: Deploy binaries into a versioned directory and activate them via symlinks (action plugin)
description:
  - Controller-side action plugin that orchestrates a remote worker module.
  - Supports controller-local sources (C(remote_src=false)) via controller->remote staging.
  - Supports remote-local sources (C(remote_src=true)) where binaries already exist on the target host.
options:
  install_dir:
    description:
      - Versioned installation directory on the target host.
    type: path
    required: true
  src_dir:
    description:
      - Directory containing extracted binaries.
      - For C(remote_src=false) this path is on the controller.
      - For C(remote_src=true) this path is on the target host.
    type: path
    required: true
  remote_src:
    description:
      - If true, C(src_dir) is on the remote host (remote->remote copy).
      - If false, C(src_dir) is on the controller (controller->remote staging).
    type: bool
    default: false
  link_dir:
    description:
      - Directory where activation symlinks are created on the target host.
    type: path
    default: /usr/bin
  items:
    description:
      - List of binaries to deploy.
      - Each item supports C(name) (required), optional C(src), optional C(link_name), optional C(capability).
    type: list
    elements: dict
    required: true
  activation_name:
    description:
      - Item name or link_name used to determine "activated" status (worker module feature).
    type: str
    required: false
  owner:
    description:
      - Owner name or uid for deployed binaries.
    type: str
    required: false
  group:
    description:
      - Group name or gid for deployed binaries.
    type: str
    required: false
  mode:
    description:
      - File mode for deployed binaries (octal string).
    type: str
    default: "0755"
  cleanup_on_failure:
    description:
      - Remove install_dir if an exception occurs during apply.
    type: bool
    default: true
author:
  - "Bodsch Core Collection"
notes:
  - This is an action plugin. It delegates actual deployment work to C(bodsch.core.deploy_and_activate_remote).
"""

EXAMPLES = r"""
- name: Deploy from controller cache (remote_src=false)
  bodsch.core.deploy_and_activate:
    remote_src: false
    src_dir: "/home/bodsch/.cache/ansible/logstream_exporter/1.0.0"
    install_dir: "/usr/local/opt/logstream_exporter/1.0.0"
    link_dir: "/usr/bin"
    owner: "logstream-exporter"
    group: "logstream-exporter"
    mode: "0755"
    items:
      - name: "logstream-exporter"
        capability: "cap_net_raw+ep"

- name: Deploy from remote extracted directory (remote_src=true)
  bodsch.core.deploy_and_activate:
    remote_src: true
    src_dir: "/var/cache/ansible/logstream_exporter/1.0.0"
    install_dir: "/usr/local/opt/logstream_exporter/1.0.0"
    items:
      - name: "logstream-exporter"
"""

RETURN = r"""
changed:
  description: Whether anything changed (as reported by the remote worker module).
  type: bool
activated:
  description: Whether the activation symlink points into install_dir (worker module result).
  type: bool
needs_update:
  description: Whether changes would be required (in probe/check mode output).
  type: bool
plan:
  description: Per-item plan (in probe/check mode output).
  type: dict
details:
  description: Per-item change details (in apply output).
  type: dict
"""


class ItemSpec(TypedDict, total=False):
    """User-facing item specification passed to the remote worker module."""

    name: str
    src: str
    link_name: str
    capability: str


@dataclass(frozen=True)
class _LocalItem:
    """Normalized local item for controller-side existence checks and staging."""

    name: str
    src_rel: str
    local_src: str


class ActionModule(ActionBase):
    """Deploy binaries to install_dir and activate them via symlinks."""

    TRANSFERS_FILES = True

    def _get_items(self, args: Mapping[str, Any]) -> List[ItemSpec]:
        """Validate and normalize the 'items' argument."""
        display.vv(f"ActionModule::_get_items(args: {dict(args)})")

        raw_items = args.get("items") or []
        if not isinstance(raw_items, list) or not raw_items:
            raise AnsibleError("deploy_and_activate: 'items' must be a non-empty list")

        out: List[ItemSpec] = []
        for idx, it in enumerate(raw_items):
            if not isinstance(it, dict):
                raise AnsibleError(f"deploy_and_activate: items[{idx}] must be a dict")
            if "name" not in it:
                raise AnsibleError(
                    f"deploy_and_activate: items[{idx}] missing required key 'name'"
                )

            name = str(it["name"]).strip()
            if not name:
                raise AnsibleError(
                    f"deploy_and_activate: items[{idx}].name must not be empty"
                )

            normalized: ItemSpec = cast(ItemSpec, dict(it))
            normalized["name"] = name
            out.append(normalized)

        return out

    def _normalize_local_items(
        self, controller_src_dir: str, items: Sequence[ItemSpec]
    ) -> List[_LocalItem]:
        """Build controller-local absolute paths for each item."""
        display.vv(
            f"ActionModule::_normalize_local_items(controller_src_dir: {controller_src_dir}, items: {list(items)})"
        )

        out: List[_LocalItem] = []
        for it in items:
            name = str(it["name"])
            src_rel = str(it.get("src") or name)
            local_src = os.path.join(controller_src_dir, src_rel)
            out.append(_LocalItem(name=name, src_rel=src_rel, local_src=local_src))
        return out

    def _ensure_local_files_exist(
        self, controller_src_dir: str, items: Sequence[ItemSpec]
    ) -> None:
        """Fail early if any controller-local binary is missing."""
        display.vv(
            f"ActionModule::_ensure_local_files_exist(controller_src_dir: {controller_src_dir}, items: {list(items)})"
        )

        for it in self._normalize_local_items(controller_src_dir, items):
            display.vv(f"= local_src: {it.local_src}, src_rel: {it.src_rel}")
            if not os.path.isfile(it.local_src):
                raise AnsibleError(
                    f"deploy_and_activate: missing extracted binary on controller: {it.local_src}"
                )

    def _probe_remote(
        self,
        *,
        tmp: Optional[str],
        task_vars: Mapping[str, Any],
        module_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the remote worker module and return its result."""
        display.vv(
            f"ActionModule::_probe_remote(tmp: {tmp}, task_vars, module_args: {module_args})"
        )

        remote = self._execute_module(
            module_name=REMOTE_WORKER_MODULE,
            module_args=module_args,
            task_vars=dict(task_vars),
            tmp=tmp,
        )
        display.vv(f"= result: {remote}")
        return remote

    def _ensure_remote_dir(
        self,
        *,
        tmp: Optional[str],
        task_vars: Mapping[str, Any],
        path: str,
        mode: str = "0700",
    ) -> None:
        """Ensure a directory exists on the remote host."""
        display.vv(
            f"ActionModule::_ensure_remote_dir(tmp: {tmp}, task_vars, path: {path}, mode: {mode})"
        )

        self._execute_module(
            module_name="ansible.builtin.file",
            module_args={"path": path, "state": "directory", "mode": mode},
            task_vars=dict(task_vars),
            tmp=tmp,
        )

    def _create_remote_temp_dir(
        self, *, tmp: Optional[str], task_vars: Mapping[str, Any]
    ) -> str:
        """
        Create a remote temporary directory.

        This avoids using ActionBase._make_tmp_path(), which is not available in all Ansible versions.
        """
        display.vv(f"ActionModule::_create_remote_temp_dir(tmp: {tmp}, task_vars)")

        res = self._execute_module(
            module_name="ansible.builtin.tempfile",
            module_args={"state": "directory", "prefix": "deploy-and-activate-"},
            task_vars=dict(task_vars),
            tmp=tmp,
        )
        path = res.get("path")
        if not path:
            raise AnsibleError(
                "deploy_and_activate: failed to create remote temporary directory"
            )
        return str(path)

    def _stage_files_to_remote(
        self,
        *,
        tmp: Optional[str],
        task_vars: Mapping[str, Any],
        controller_src_dir: str,
        items: Sequence[ItemSpec],
    ) -> Tuple[str, bool]:
        """
        Stage controller-local files onto the remote host via ActionBase._transfer_file().

        Returns:
            Tuple(remote_stage_dir, created_by_us)
        """
        normalized = self._normalize_local_items(controller_src_dir, items)

        if tmp:
            remote_stage_dir = tmp
            created_by_us = False
        else:
            remote_stage_dir = self._create_remote_temp_dir(
                tmp=tmp, task_vars=task_vars
            )
            created_by_us = True

        display.vv(
            f"ActionModule::_stage_files_to_remote(remote_stage_dir: {remote_stage_dir}, created_by_us: {created_by_us})"
        )

        self._ensure_remote_dir(
            tmp=tmp, task_vars=task_vars, path=remote_stage_dir, mode="0700"
        )

        # Create required subdirectories on remote if src_rel contains paths.
        needed_dirs: Set[str] = set()
        for it in normalized:
            rel_dir = os.path.dirname(it.src_rel)
            if rel_dir and rel_dir not in (".", "/"):
                needed_dirs.add(os.path.join(remote_stage_dir, rel_dir))

        for d in sorted(needed_dirs):
            self._ensure_remote_dir(tmp=tmp, task_vars=task_vars, path=d, mode="0700")

        # Transfer files.
        for it in normalized:
            remote_dst = os.path.join(remote_stage_dir, it.src_rel)
            display.vv(f"ActionModule::_transfer_file({it.local_src} -> {remote_dst})")
            self._transfer_file(it.local_src, remote_dst)

        return remote_stage_dir, created_by_us

    def run(
        self, tmp: str | None = None, task_vars: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Action plugin entrypoint.

        Args:
            tmp: Remote tmp directory (may be None depending on Ansible execution path).
            task_vars: Task variables.

        Returns:
            Result dict compatible with Ansible task output.
        """
        display.vv(f"ActionModule::run(tmp: {tmp}, task_vars)")

        if task_vars is None:
            task_vars = {}

        _ = super().run(tmp, task_vars)
        args: Dict[str, Any] = self._task.args.copy()

        remote_src = bool(args.get("remote_src", False))
        install_dir = str(args["install_dir"])
        link_dir = str(args.get("link_dir", "/usr/bin"))
        src_dir = args.get("src_dir")
        mode = str(args.get("mode", "0755"))
        owner = args.get("owner")
        group = args.get("group")
        cleanup_on_failure = bool(args.get("cleanup_on_failure", True))
        activation_name = args.get("activation_name")

        items = self._get_items(args)

        display.vv(f" - remote_src         : {remote_src}")
        display.vv(f" - install_dir        : {install_dir}")
        display.vv(f" - src_dir            : {src_dir}")
        display.vv(f" - link_dir           : {link_dir}")
        display.vv(f" - owner              : {owner}")
        display.vv(f" - group              : {group}")
        display.vv(f" - cleanup_on_failure : {cleanup_on_failure}")
        display.vv(f" - activation_name    : {activation_name}")

        # --- Probe (remote) ---
        probe_args: Dict[str, Any] = {
            "install_dir": install_dir,
            "link_dir": link_dir,
            "items": list(items),
            "activation_name": activation_name,
            "owner": owner,
            "group": group,
            "mode": mode,
            "cleanup_on_failure": cleanup_on_failure,
            "check_only": True,
            "copy": remote_src,
        }

        if remote_src:
            if not src_dir:
                raise AnsibleError(
                    "deploy_and_activate: 'src_dir' is required when remote_src=true (remote path)"
                )
            probe_args["src_dir"] = str(src_dir)

        display.vv(f" - probe_args         : {probe_args}")
        probe = self._probe_remote(tmp=tmp, task_vars=task_vars, module_args=probe_args)

        # Check mode: never change.
        if bool(task_vars.get("ansible_check_mode", False)):
            probe["changed"] = False
            return probe

        # Early exit if nothing to do.
        if not probe.get("needs_update", False):
            probe["changed"] = False
            return probe

        # --- Apply ---
        stage_dir: Optional[str] = None
        stage_created_by_us = False

        try:
            self._ensure_remote_dir(
                tmp=tmp, task_vars=task_vars, path=install_dir, mode="0755"
            )

            if remote_src:
                apply_args = dict(probe_args)
                apply_args["check_only"] = False
                apply_args["copy"] = True
                apply_args["src_dir"] = str(src_dir)
                return self._probe_remote(
                    tmp=tmp, task_vars=task_vars, module_args=apply_args
                )

            # Controller -> Remote staging -> Remote apply(copy=True)
            if not src_dir:
                raise AnsibleError(
                    "deploy_and_activate: 'src_dir' is required when remote_src=false (controller path)"
                )

            controller_src_dir = str(src_dir)
            self._ensure_local_files_exist(controller_src_dir, items)

            stage_dir, stage_created_by_us = self._stage_files_to_remote(
                tmp=tmp,
                task_vars=task_vars,
                controller_src_dir=controller_src_dir,
                items=items,
            )

            apply_args = {
                "install_dir": install_dir,
                "link_dir": link_dir,
                "items": list(items),
                "activation_name": activation_name,
                "owner": owner,
                "group": group,
                "mode": mode,
                "cleanup_on_failure": cleanup_on_failure,
                "check_only": False,
                "copy": True,
                "src_dir": stage_dir,
            }
            return self._probe_remote(
                tmp=tmp, task_vars=task_vars, module_args=apply_args
            )

        except Exception:
            if cleanup_on_failure:
                try:
                    self._execute_module(
                        module_name="ansible.builtin.file",
                        module_args={"path": install_dir, "state": "absent"},
                        task_vars=dict(task_vars),
                        tmp=tmp,
                    )
                except Exception:
                    pass
            raise

        finally:
            # Best-effort cleanup of the remote staging dir only if we created it.
            if stage_dir and stage_created_by_us:
                try:
                    self._execute_module(
                        module_name="ansible.builtin.file",
                        module_args={"path": stage_dir, "state": "absent"},
                        task_vars=dict(task_vars),
                        tmp=tmp,
                    )
                except Exception:
                    pass
