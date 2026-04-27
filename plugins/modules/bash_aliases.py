#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to manage bash aliases and functions for many users efficiently.

This module is designed to be invoked once per host while handling a large list of
users within the module (to avoid slow Ansible task loops and SSH round-trips).

Key properties:
- Validates users and their home directories.
- Renders deterministic alias and function files in each user's home directory.
- Optionally manages a marker block in the user's .bashrc to source the managed files.
- Idempotent: writes occur only when the target content differs.
- Safe updates: atomic file replacement.
- Optional backups on change/remove.
- Continues processing all users, collects per-user results, and optionally fails at the end.

No subprocess usage.
"""

from __future__ import annotations

import os
import pwd
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: bash_aliases
version_added: 2.11.0
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Manage bash aliases and functions for many users (idempotent, fast)
description:
  - Validates users and their home directories.
  - Writes deterministic alias and function files into each user's home directory.
  - Optionally ensures C(.bashrc) sources these files via a managed marker block.
  - Designed to avoid Ansible task loops by handling all users in a single module run.
  - Continues processing all users and collects results; optionally fails at end if any user failed.

options:
  users:
    description:
      - List of user specifications.
      - Unknown users do not stop processing; they are reported as failed in the result.
    type: list
    elements: dict
    required: true
    suboptions:
      name:
        description: Username to manage.
        type: str
        required: true
      aliases:
        description: List of alias definitions for this user.
        type: list
        elements: dict
        required: false
        default: []
        suboptions:
          alias:
            description: Alias name (bash identifier).
            type: str
            required: true
          command:
            description: Alias command.
            type: str
            required: true
          comment:
            description: Optional comment line preceding the alias.
            type: str
            required: false
      functions:
        description: List of bash function definitions for this user.
        type: list
        elements: dict
        required: false
        default: []
        suboptions:
          name:
            description: Function name (bash identifier).
            type: str
            required: true
          content:
            description: Function body (multi-line supported).
            type: str
            required: true
          comment:
            description: Optional comment line preceding the function.
            type: str
            required: false
      manage_bashrc:
        description: Manage a marker block in user's C(.bashrc) to source managed files.
        type: bool
        required: false
        default: true
      aliases_filename:
        description: Alias filename within the user's home directory.
        type: str
        required: false
        default: ".bash_aliases"
      functions_filename:
        description: Functions filename within the user's home directory.
        type: str
        required: false
        default: ".bash_functions"
      bashrc_filename:
        description: Bashrc filename within the user's home directory.
        type: str
        required: false
        default: ".bashrc"
  common_aliases:
    description: Aliases applied to every user (prepended).
    type: list
    elements: dict
    required: false
    default: []
  common_functions:
    description: Functions applied to every user (prepended).
    type: list
    elements: dict
    required: false
    default: []
  state:
    description:
      - Whether managed files and bashrc block should exist.
      - C(absent) removes managed files and the marker block from C(.bashrc).
    type: str
    required: false
    default: present
    choices: [present, absent]
  backup:
    description: Create backups of files before changing or deleting them.
    type: bool
    required: false
    default: false
  fail_on_error:
    description:
      - If true, the task fails at the end when any user entry failed, but still returns full results.
      - If false, returns success and reports failures in results/summary.
    type: bool
    required: false
    default: true
notes:
  - The module writes files as mode C(0644) and sets ownership to the target user.
  - If C(manage_bashrc=true) and the user's C(.bashrc) does not exist, the module creates it with the managed block only.
"""

EXAMPLES = r"""
- name: Manage bash aliases/functions for many users in one task
  become: true
  bodsch.core.bash_aliases:
    state: present
    backup: true
    fail_on_error: true
    common_aliases:
      - alias: ll
        command: "ls -lah"
    users:
      - name: alice
        aliases:
          - alias: foo
            command: "echo 'foo'"
        functions:
          - name: mkcd
            content: |
              mkdir -p "$1" && cd "$1"
      - name: bob
        manage_bashrc: true
        aliases: []
        functions: []

- name: Remove managed files and bashrc blocks
  become: true
  bash_aliases:
    state: absent
    users:
      - name: alice
      - name: bob
"""

RETURN = r"""
changed:
  description: Whether any file was created/updated/removed.
  returned: always
  type: bool
summary:
  description: Summary of processed users.
  returned: always
  type: dict
  sample:
    total: 2
    ok: 1
    failed: 1
    failed_users: ["unknownuser"]
results:
  description: Per-user summary including failures and file actions.
  returned: always
  type: list
  elements: dict
  sample:
    - user: alice
      status: ok
      changed: true
      files:
        - path: /home/alice/.bash_aliases
          action: updated
          backup: /home/alice/.bash_aliases.12345.2026-03-12@12:00~
        - path: /home/alice/.bashrc
          action: updated
          backup: /home/alice/.bashrc.12345.2026-03-12@12:00~
    - user: unknownuser
      status: failed
      changed: false
      error: "User does not exist: 'unknownuser'"
      files: []
"""

_ALIAS_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FUNC_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_MARKER_BEGIN = "# BEGIN ANSIBLE MANAGED BASH ALIASES"
_MARKER_END = "# END ANSIBLE MANAGED BASH ALIASES"


@dataclass(frozen=True)
class AliasSpec:
    """Validated alias specification."""

    name: str
    command: str
    comment: str = ""


@dataclass(frozen=True)
class FunctionSpec:
    """Validated bash function specification."""

    name: str
    content: str
    comment: str = ""


@dataclass(frozen=True)
class UserSpec:
    """Validated per-user configuration."""

    name: str
    home: str
    uid: int
    gid: int
    manage_bashrc: bool
    aliases_filename: str
    functions_filename: str
    bashrc_filename: str
    aliases: Tuple[AliasSpec, ...]
    functions: Tuple[FunctionSpec, ...]


@dataclass(frozen=True)
class FileChange:
    """Represents a single file action and an optional backup path."""

    path: str
    action: str  # created|updated|removed|unchanged
    backup: Optional[str] = None


class BashAliasManager:
    """
    Apply the desired alias/function configuration for many users.

    Public API:
      - execute(): Returns a result dict suitable for module.exit_json/module.fail_json.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the manager from module parameters.

        Args:
            module: AnsibleModule instance.
        """
        self._module = module
        self._state: str = str(module.params["state"])
        self._backup: bool = bool(module.params["backup"])
        self._fail_on_error: bool = bool(module.params["fail_on_error"])
        self._check_mode: bool = bool(module.check_mode)

        self._users_param: Sequence[Mapping[str, Any]] = module.params["users"] or []
        self._common_aliases_param: Sequence[Mapping[str, Any]] = (
            module.params["common_aliases"] or []
        )
        self._common_functions_param: Sequence[Mapping[str, Any]] = (
            module.params["common_functions"] or []
        )

    def run(self) -> Dict[str, Any]:
        """
        Execute the module logic for all users.

        Returns:
            A dict containing changed/results/summary. If failures occurred and
            fail_on_error is true, the returned dict includes failed=True and msg.
        """
        common_aliases = self._validate_aliases(
            self._common_aliases_param, scope="common_aliases"
        )
        common_functions = self._validate_functions(
            self._common_functions_param, scope="common_functions"
        )

        overall_changed = False
        results: List[Dict[str, Any]] = []
        failed_users: List[str] = []

        for entry in self._users_param:
            name = str(entry.get("name", "")).strip() or "<missing-name>"
            try:
                user_spec = self._build_user_spec(entry)
                user_changed, files = self._apply_user(
                    state=self._state,
                    user=user_spec,
                    common_aliases=common_aliases,
                    common_functions=common_functions,
                )
                overall_changed = overall_changed or user_changed
                results.append(
                    {
                        "user": user_spec.name,
                        "status": "ok",
                        "changed": user_changed,
                        # TODO
                        # only with enabled `verbose` flag
                        # "files": [fc.__dict__ for fc in files],
                    }
                )
            except Exception as exc:
                failed_users.append(name)
                results.append(
                    {
                        "user": name,
                        "status": "failed",
                        "changed": False,
                        "error": str(exc),
                        # "files": [],
                    }
                )

        # summary = {
        #     "total": len(self._users_param),
        #     "ok": len(self._users_param) - len(failed_users),
        #     "failed": len(failed_users),
        #     "failed_users": failed_users,
        # }

        if failed_users and self._fail_on_error:
            return {
                "failed": True,
                "changed": overall_changed,
                "msg": "One or more users failed. See results/summary for details.",
                "results": results,
                # "summary": summary,
            }

        return {
            "changed": overall_changed,
            "results": results,
            # "summary": summary
        }

    def _apply_user(
        self,
        state: str,
        user: UserSpec,
        common_aliases: Tuple[AliasSpec, ...],
        common_functions: Tuple[FunctionSpec, ...],
    ) -> Tuple[bool, List[FileChange]]:
        """
        Apply desired state for a single user.

        Args:
            state: 'present' or 'absent'
            user: Validated UserSpec
            common_aliases: aliases to prepend
            common_functions: functions to prepend

        Returns:
            (changed, file_changes)
        """
        changed = False
        files: List[FileChange] = []

        aliases_path = os.path.join(user.home, user.aliases_filename)
        functions_path = os.path.join(user.home, user.functions_filename)
        bashrc_path = os.path.join(user.home, user.bashrc_filename)

        if state == "present":
            aliases_content = self._render_aliases(
                tuple(common_aliases) + tuple(user.aliases)
            )
            functions_content = self._render_functions(
                tuple(common_functions) + tuple(user.functions)
            )

            changed |= self._ensure_file(aliases_path, aliases_content, user, files)
            changed |= self._ensure_file(functions_path, functions_content, user, files)

            if user.manage_bashrc:
                block = self._bashrc_block(aliases_path, functions_path)
                changed |= self._ensure_bashrc_block(bashrc_path, block, user, files)

        elif state == "absent":
            changed |= self._remove_if_exists(aliases_path, files)
            changed |= self._remove_if_exists(functions_path, files)

            exists, bashrc_current = self._read_text(bashrc_path)
            if exists and bashrc_current is not None:
                needs, new_content = self._remove_bashrc_block(bashrc_current)
                if needs:
                    bkp = self._maybe_backup(bashrc_path)
                    self._atomic_write_text(
                        bashrc_path,
                        new_content,
                        mode=0o644,
                        uid=user.uid,
                        gid=user.gid,
                        check_executemode=self._check_mode,
                    )
                    changed = True
                    files.append(
                        FileChange(path=bashrc_path, action="updated", backup=bkp)
                    )
                else:
                    files.append(FileChange(path=bashrc_path, action="unchanged"))
            else:
                files.append(FileChange(path=bashrc_path, action="unchanged"))

        else:
            raise ValueError(f"Unsupported state: {state!r}")

        return changed, files

    def _maybe_backup(self, path: str) -> Optional[str]:
        """
        Create a backup of path if enabled and file exists.

        Returns:
            Backup path or None.
        """
        if self._check_mode:
            return None
        if not self._backup:
            return None
        if not os.path.exists(path):
            return None
        return self._module.backup_local(path)

    def _ensure_file(
        self, path: str, content: str, user: UserSpec, files: List[FileChange]
    ) -> bool:
        """
        Ensure file exists with exact content.

        Returns:
            True if changed, else False.
        """
        exists, current = self._read_text(path)
        desired = content if content.endswith("\n") else (content + "\n")

        if not exists or current is None:
            bkp = self._maybe_backup(path)
            self._atomic_write_text(
                path,
                desired,
                mode=0o644,
                uid=user.uid,
                gid=user.gid,
                check_mode=self._check_mode,
            )
            files.append(FileChange(path=path, action="created", backup=bkp))
            return True

        if current != desired:
            bkp = self._maybe_backup(path)
            self._atomic_write_text(
                path,
                desired,
                mode=0o644,
                uid=user.uid,
                gid=user.gid,
                check_mode=self._check_mode,
            )
            files.append(FileChange(path=path, action="updated", backup=bkp))
            return True

        files.append(FileChange(path=path, action="unchanged"))
        return False

    def _remove_if_exists(self, path: str, files: List[FileChange]) -> bool:
        """
        Remove file if it exists.

        Returns:
            True if removed, else False.
        """
        if not os.path.exists(path):
            files.append(FileChange(path=path, action="unchanged"))
            return False
        bkp = self._maybe_backup(path)
        self._remove_file(path, check_mode=self._check_mode)
        files.append(FileChange(path=path, action="removed", backup=bkp))
        return True

    @staticmethod
    def _bashrc_block(aliases_path: str, functions_path: str) -> str:
        """
        Build the managed .bashrc marker block.

        The block is replaced as a whole if it already exists.
        """
        return "\n".join(
            [
                _MARKER_BEGIN,
                "# Managed by Ansible module bash_aliases.",
                f'if [ -f "{aliases_path}" ]; then',
                f'  . "{aliases_path}"',
                "fi",
                f'if [ -f "{functions_path}" ]; then',
                f'  . "{functions_path}"',
                "fi",
                _MARKER_END,
                "",
            ]
        )

    def _ensure_bashrc_block(
        self, bashrc_path: str, block: str, user: UserSpec, files: List[FileChange]
    ) -> bool:
        """
        Ensure .bashrc contains the desired marker block (replace or append).

        Returns:
            True if changed, else False.
        """
        exists, existing = self._read_text(bashrc_path)
        existing_text = existing or ""
        desired_block = block.strip("\n")

        begin = existing_text.find(_MARKER_BEGIN)
        end = existing_text.find(_MARKER_END)

        if begin != -1 and end != -1 and end > begin:
            current_block = existing_text[begin: end + len(_MARKER_END)].strip("\n")
            if current_block == desired_block:
                files.append(FileChange(path=bashrc_path, action="unchanged"))
                return False
            pre = existing_text[:begin].rstrip("\n")
            post = existing_text[end + len(_MARKER_END):].lstrip("\n")
            merged = (pre + "\n" + desired_block + "\n" + post).rstrip("\n") + "\n"
        else:
            merged = (
                existing_text.rstrip("\n") + "\n\n" + desired_block + "\n"
            ).lstrip("\n")

        if merged == existing_text:
            files.append(FileChange(path=bashrc_path, action="unchanged"))
            return False

        bkp = self._maybe_backup(bashrc_path)
        self._atomic_write_text(
            bashrc_path,
            merged,
            mode=0o644,
            uid=user.uid,
            gid=user.gid,
            check_mode=self._check_mode,
        )
        files.append(
            FileChange(
                path=bashrc_path,
                action=("created" if not exists else "updated"),
                backup=bkp,
            )
        )
        return True

    @staticmethod
    def _validate_filename(name: Any, field: str) -> str:
        """
        Validate that filenames are simple basenames (no path separators).

        Args:
            name: Raw filename value.
            field: Parameter name (for error messages).

        Returns:
            Validated basename.
        """
        n = str(name).strip()
        if not n:
            raise ValueError(f"{field} must not be empty")
        if "/" in n or "\x00" in n:
            raise ValueError(f"{field} must be a basename without '/' or NUL: {n!r}")
        return n

    @staticmethod
    def _validate_aliases(
        raw: Sequence[Mapping[str, Any]], scope: str
    ) -> Tuple[AliasSpec, ...]:
        """
        Validate and normalize alias specs.

        Args:
            raw: Raw alias list.
            scope: Name of the parameter scope for better error messages.

        Returns:
            Tuple of AliasSpec.
        """
        out: List[AliasSpec] = []
        for idx, item in enumerate(raw):
            name = str(item.get("alias", "")).strip()
            cmd = str(item.get("command", "")).strip()
            comment = str(item.get("comment", "") or "").strip()

            if not name or not _ALIAS_NAME_RE.match(name):
                raise ValueError(f"{scope}[{idx}].alias: invalid alias name: {name!r}")
            if cmd == "":
                raise ValueError(
                    f"{scope}[{idx}].command: must not be empty for alias {name!r}"
                )

            out.append(AliasSpec(name=name, command=cmd, comment=comment))
        return tuple(out)

    @staticmethod
    def _validate_functions(
        raw: Sequence[Mapping[str, Any]], scope: str
    ) -> Tuple[FunctionSpec, ...]:
        """
        Validate and normalize function specs.

        Args:
            raw: Raw function list.
            scope: Name of the parameter scope for better error messages.

        Returns:
            Tuple of FunctionSpec.
        """
        out: List[FunctionSpec] = []
        for idx, item in enumerate(raw):
            name = str(item.get("name", "")).strip()
            content = str(item.get("content", "")).rstrip()
            comment = str(item.get("comment", "") or "").strip()

            if not name or not _FUNC_NAME_RE.match(name):
                raise ValueError(
                    f"{scope}[{idx}].name: invalid function name: {name!r}"
                )
            if content.strip() == "":
                raise ValueError(
                    f"{scope}[{idx}].content: must not be empty for function {name!r}"
                )

            out.append(FunctionSpec(name=name, content=content, comment=comment))
        return tuple(out)

    def _build_user_spec(self, entry: Mapping[str, Any]) -> UserSpec:
        """
        Build a validated UserSpec from a single users[] entry.

        Raises:
            ValueError: If user is missing/unknown, home is invalid, or definitions are invalid.
        """
        name = str(entry.get("name", "")).strip()
        if not name:
            raise ValueError("users[] entry must include a non-empty 'name'")

        try:
            pw = pwd.getpwnam(name)
        except KeyError:
            raise ValueError(f"User does not exist: {name!r}") from None

        home = pw.pw_dir
        if not home or not os.path.isabs(home) or not os.path.isdir(home):
            raise ValueError(
                f"User {name!r} has invalid or missing home directory: {home!r}"
            )

        manage_bashrc = bool(entry.get("manage_bashrc", True))
        aliases_filename = self._validate_filename(
            entry.get("aliases_filename", ".bash_aliases"), "aliases_filename"
        )
        functions_filename = self._validate_filename(
            entry.get("functions_filename", ".bash_functions"), "functions_filename"
        )
        bashrc_filename = self._validate_filename(
            entry.get("bashrc_filename", ".bashrc"), "bashrc_filename"
        )

        aliases_raw = entry.get("aliases", []) or []
        funcs_raw = entry.get("functions", []) or []

        aliases = self._validate_aliases(aliases_raw, scope=f"users[{name}].aliases")
        functions = self._validate_functions(
            funcs_raw, scope=f"users[{name}].functions"
        )

        return UserSpec(
            name=name,
            home=home,
            uid=pw.pw_uid,
            gid=pw.pw_gid,
            manage_bashrc=manage_bashrc,
            aliases_filename=aliases_filename,
            functions_filename=functions_filename,
            bashrc_filename=bashrc_filename,
            aliases=aliases,
            functions=functions,
        )

    @staticmethod
    def _bash_single_quote(value: str) -> str:
        """
        Quote a string for bash using single quotes, escaping embedded single quotes.

        Example:
            abc'def -> 'abc'"'"'def'
        """
        return "'" + value.replace("'", "'\"'\"'") + "'"

    def _render_aliases(self, aliases: Sequence[AliasSpec]) -> str:
        """
        Render deterministic .bash_aliases content.

        Args:
            aliases: Alias specifications.

        Returns:
            File content.
        """
        lines: List[str] = [
            "# Managed by Ansible module bash_aliases. Do not edit manually.",
            "",
        ]
        for a in aliases:
            if a.comment:
                lines.append(f"# {a.comment}")
            lines.append(f"alias {a.name}={self._bash_single_quote(a.command)}")
        lines.append("")
        return "\n".join(lines)

    def _render_functions(self, functions: Sequence[FunctionSpec]) -> str:
        """
        Render deterministic .bash_functions content.

        Args:
            functions: Function specifications.

        Returns:
            File content.
        """
        lines: List[str] = [
            "# Managed by Ansible module bash_aliases. Do not edit manually.",
            "",
        ]
        for fn in functions:
            if fn.comment:
                lines.append(f"# {fn.comment}")
            lines.append(f"{fn.name}() {{")
            body = fn.content.strip("\n")
            for bline in body.splitlines():
                lines.append(f"  {bline.rstrip()}")
            lines.append("}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _read_text(path: str) -> Tuple[bool, Optional[str]]:
        """
        Read a text file.

        Returns:
            (exists, content). If the file exists but cannot be read, content is None.
        """
        if not os.path.exists(path):
            return False, None
        try:
            with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
                return True, f.read()
        except OSError:
            return True, None

    @staticmethod
    def _atomic_write_text(
        path: str, content: str, mode: int, uid: int, gid: int, check_mode: bool
    ) -> None:
        """
        Write file atomically with desired ownership and permissions.

        Args:
            path: Target path.
            content: Desired content.
            mode: File mode.
            uid: Owner UID.
            gid: Owner GID.
            check_mode: Whether to skip actual writes.
        """
        if check_mode:
            return

        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(prefix=".ansible-bash-alias-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")

            os.chmod(tmp_path, mode)
            os.chown(tmp_path, uid, gid)
            os.replace(tmp_path, path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _remove_file(path: str, check_mode: bool) -> None:
        """
        Remove a file if it exists.

        Args:
            path: File path.
            check_mode: Whether to skip actual deletion.
        """
        if check_mode:
            return
        try:
            os.unlink(path)
        except FileNotFoundError:
            return

    @staticmethod
    def _remove_bashrc_block(existing: str) -> Tuple[bool, str]:
        """
        Remove marker block from bashrc content.

        Returns:
            (changed, new_content)
        """
        begin = existing.find(_MARKER_BEGIN)
        end = existing.find(_MARKER_END)
        if begin == -1 or end == -1 or end <= begin:
            return False, existing

        pre = existing[:begin].rstrip("\n")
        post = existing[end + len(_MARKER_END):].lstrip("\n")
        new_content = (pre + "\n" + post).strip("\n") + "\n"
        if new_content == existing:
            return False, existing
        return True, new_content


def main() -> None:
    """Ansible module entrypoint."""
    argument_spec = dict(
        users=dict(type="list", elements="dict", required=True),
        common_aliases=dict(type="list", elements="dict", required=False, default=[]),
        common_functions=dict(type="list", elements="dict", required=False, default=[]),
        state=dict(
            type="str", required=False, default="present", choices=["present", "absent"]
        ),
        backup=dict(type="bool", required=False, default=False),
        fail_on_error=dict(type="bool", required=False, default=True),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    try:
        manager = BashAliasManager(module)
        result = manager.run()
    except Exception as exc:
        module.fail_json(msg=f"Unhandled error: {exc}")

    if result.get("failed"):
        module.fail_json(**result)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
