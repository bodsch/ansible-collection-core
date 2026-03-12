#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to manage bash aliases and functions for multiple users efficiently.

Key properties:
- Single module invocation per host (avoid Ansible task loops).
- Validates users + home directories.
- Idempotent file rendering based on exact desired content.
- Atomic writes (safe updates).
- Optional backups for changed/removed files.
- Continues processing all users; collects per-user results; optionally fails at end.

No subprocess usage.
"""

from __future__ import annotations

import os
import pwd
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ansible.module_utils import distro
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: bash_aliases
version_added: 2.11.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

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
    required: true
    type: list
    elements: dict
    suboptions:
      name:
        description: Username to manage.
        required: true
        type: str
      aliases:
        description: List of alias definitions for this user.
        required: false
        type: list
        elements: dict
        suboptions:
          alias:
            type: str
            required: true
          command:
            type: str
            required: true
          comment:
            type: str
            required: false
      functions:
        description: List of bash function definitions for this user.
        required: false
        type: list
        elements: dict
        suboptions:
          name:
            type: str
            required: true
          content:
            type: str
            required: true
          comment:
            type: str
            required: false
      manage_bashrc:
        description: Manage a marker block in user's .bashrc to source managed files.
        type: bool
        default: true
      aliases_filename:
        description: Alias filename within the user's home directory.
        type: str
        default: ".bash_aliases"
      functions_filename:
        description: Functions filename within the user's home directory.
        type: str
        default: ".bash_functions"
      bashrc_filename:
        description: Bashrc filename within the user's home directory.
        type: str
        default: ".bashrc"
  common_aliases:
    description: Aliases applied to every user (prepended).
    type: list
    default: []
    elements: dict
  common_functions:
    description: Functions applied to every user (prepended).
    type: list
    default: []
    elements: dict
  state:
    description:
      - Whether managed files and bashrc block should exist.
      - C(absent) removes managed files and the marker block from .bashrc.
    type: str
    default: present
    choices: [present, absent]
  backup:
    description: Create backups of files before changing or deleting them.
    type: bool
    default: true
  fail_on_error:
    description:
      - If true, the task fails at the end when any user entry failed, but still returns full results.
      - If false, returns success and reports failures in results/summary.
    type: bool
    default: true
"""

EXAMPLES = r"""
- name: Manage bash aliases/functions for many users in one task
  become: true
  bash_alias_manage:
    state: present
    backup: true
    fail_on_error: true
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
    common_aliases:
      - alias: ll
        command: "ls -lah"

- name: Remove managed files and bashrc blocks
  become: true
  bash_alias_manage:
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
results:
  description: Per-user summary including failures.
  returned: always
  type: list
  elements: dict
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
    """Represents a single file action and optional backup path."""

    path: str
    action: str  # created|updated|removed|unchanged
    backup: Optional[str] = None


class BashAliasManager:
    """Core implementation that applies desired state for configured users."""

    def __init__(self, module: AnsibleModule) -> None:
        """ """

        self.module = module
        self.module.log("BashAliasManager::__init__()")

        self.state = str(module.params["state"])
        self.fail_on_error = bool(module.params["fail_on_error"])

        self.common_aliases = module.params["common_aliases"] or []
        self.common_functions = module.params["common_functions"] or []

        self.users = module.params["users"] or []

        self._backup = bool(module.params["backup"])
        self._check = bool(module.check_mode)

        self.distribution = distro.id()
        self.version = distro.version()
        self.codename = distro.codename()

        self.module.log(
            msg=f"  - pkg       : {self.distribution} - {self.version} - {self.codename}"
        )

    def run(self):
        """ """
        self.module.log("BashAliasManager::run()")

        # Validate common specs once
        try:
            common_aliases = self._validate_aliases(self.common_aliases)
            common_functions = self._validate_functions(self.common_functions)
        except ValueError:
            self.module.fail_json("Invalid common_* definition")

        results: List[Dict[str, Any]] = []
        overall_changed = False
        failed_users: List[str] = []

        users_param: Sequence[Mapping[str, Any]] = self.users

        for entry in users_param:
            name = str(entry.get("name", "")).strip() or "<missing-name>"
            try:
                user_spec = self._build_user_spec(entry)
                user_changed, files = self.apply_user(
                    state=self.state,
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
                        # "files": [fc.__dict__ for fc in files],
                    }
                )
            except Exception as e:
                failed_users.append(name)
                results.append(
                    {
                        "user": name,
                        "failed": True,
                        "changed": False,
                        "error": str(e),
                        # "files": [],
                    }
                )

        if failed_users and self.fail_on_error:
            self.module.fail_json(
                failed=True,
                changed=overall_changed,
                msg="One or more users failed. See results/summary for details.",
                results=results,
            )

        self.module.exit_json(
            failed=False,
            changed=overall_changed,
            results=results,
        )

    def _maybe_backup(self, path: str) -> Optional[str]:
        """Create a backup of path if enabled and file exists."""

        self.module.log(f"BashAliasManager::_maybe_backup(path: {path})")

        if self._check:
            return None
        if not self._backup:
            return None
        if not os.path.exists(path):
            return None
        return self.module.backup_local(path)

    def apply_user(
        self,
        state: str,
        user: UserSpec,
        common_aliases: Tuple[AliasSpec, ...],
        common_functions: Tuple[FunctionSpec, ...],
    ) -> Tuple[bool, List[FileChange]]:
        """Apply desired state for a single user."""

        self.module.log(
            f"BashAliasManager::apply_user(state: {state}, user: {user}, common_aliases: {common_aliases}, common_functions: {common_functions})"
        )

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

            bashrc_current = self._read_text(bashrc_path)
            if bashrc_current is not None:
                needs, new_content = self._remove_bashrc_block(bashrc_current)
                if needs:
                    bkp = self._maybe_backup(bashrc_path)
                    self._atomic_write_text(
                        bashrc_path,
                        new_content,
                        mode=0o644,
                        uid=user.uid,
                        gid=user.gid,
                        check_mode=self._check,
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

    def _ensure_file(
        self, path: str, content: str, user: UserSpec, files: List[FileChange]
    ) -> bool:
        """Ensure file exists with exact content."""
        self.module.log(
            f"BashAliasManager::_ensure_file(path: {path}, content: {content}, user: {user}, files: {files})"
        )

        current = self._read_text(path)
        desired = content if content.endswith("\n") else (content + "\n")

        if current is None:
            bkp = self._maybe_backup(path)
            self._atomic_write_text(
                path,
                desired,
                mode=0o644,
                uid=user.uid,
                gid=user.gid,
                check_mode=self._check,
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
                check_mode=self._check,
            )
            files.append(FileChange(path=path, action="updated", backup=bkp))
            return True

        files.append(FileChange(path=path, action="unchanged"))
        return False

    def _remove_if_exists(self, path: str, files: List[FileChange]) -> bool:
        """Remove file if it exists."""
        self.module.log(
            f"BashAliasManager::_remove_if_exists(path: {path}, files: {files})"
        )

        if not os.path.exists(path):
            files.append(FileChange(path=path, action="unchanged"))
            return False
        bkp = self._maybe_backup(path)
        self._remove_file(path, check_mode=self._check)
        files.append(FileChange(path=path, action="removed", backup=bkp))
        return True

    @staticmethod
    def _bashrc_block(aliases_path: str, functions_path: str) -> str:
        """Build the managed .bashrc marker block."""
        return "\n".join(
            [
                _MARKER_BEGIN,
                "# Managed by Ansible module bash_alias_manage.",
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
        """Ensure .bashrc contains the desired marker block (replace or append)."""
        self.module.log(
            f"BashAliasManager::_ensure_bashrc_block(bashrc_path: {bashrc_path}, block: {block}, user: {user}, files: {files})"
        )

        existing = self._read_text(bashrc_path) or ""
        desired_block = block.strip("\n")

        begin = existing.find(_MARKER_BEGIN)
        end = existing.find(_MARKER_END)

        if begin != -1 and end != -1 and end > begin:
            current_block = existing[begin : end + len(_MARKER_END)].strip("\n")
            if current_block == desired_block:
                files.append(FileChange(path=bashrc_path, action="unchanged"))
                return False
            pre = existing[:begin].rstrip("\n")
            post = existing[end + len(_MARKER_END) :].lstrip("\n")
            merged = (pre + "\n" + desired_block + "\n" + post).rstrip("\n") + "\n"
        else:
            merged = (existing.rstrip("\n") + "\n\n" + desired_block + "\n").lstrip(
                "\n"
            )

        if merged == existing:
            files.append(FileChange(path=bashrc_path, action="unchanged"))
            return False

        bkp = self._maybe_backup(bashrc_path)
        self._atomic_write_text(
            bashrc_path,
            merged,
            mode=0o644,
            uid=user.uid,
            gid=user.gid,
            check_mode=self._check,
        )
        files.append(
            FileChange(
                path=bashrc_path,
                action=("created" if existing == "" else "updated"),
                backup=bkp,
            )
        )
        return True

    def _validate_aliases(
        self, raw: Sequence[Mapping[str, Any]]
    ) -> Tuple[AliasSpec, ...]:
        """Validate and normalize alias specs."""
        self.module.log(f"BashAliasManager::_validate_aliases(raw: {raw})")

        out: List[AliasSpec] = []
        for item in raw:
            name = str(item.get("alias", "")).strip()
            cmd = str(item.get("command", "")).strip()
            comment = str(item.get("comment", "") or "").strip()

            if not name or not _ALIAS_NAME_RE.match(name):
                raise ValueError(f"Invalid alias name: {name!r}")
            if cmd == "":
                raise ValueError(f"Alias command must not be empty for alias {name!r}")

            out.append(AliasSpec(name=name, command=cmd, comment=comment))
        return tuple(out)

    def _validate_functions(
        self, raw: Sequence[Mapping[str, Any]]
    ) -> Tuple[FunctionSpec, ...]:
        """Validate and normalize function specs."""
        self.module.log(f"BashAliasManager::_validate_functions(raw: {raw})")

        out: List[FunctionSpec] = []
        for item in raw:
            name = str(item.get("name", "")).strip()
            content = str(item.get("content", "")).rstrip()
            comment = str(item.get("comment", "") or "").strip()

            if not name or not _FUNC_NAME_RE.match(name):
                raise ValueError(f"Invalid function name: {name!r}")
            if content.strip() == "":
                raise ValueError(
                    f"Function content must not be empty for function {name!r}"
                )

            out.append(FunctionSpec(name=name, content=content, comment=comment))
        return tuple(out)

    def _build_user_spec(self, entry: Mapping[str, Any]) -> UserSpec:
        """Build a validated UserSpec from a single users[] entry."""
        self.module.log(f"BashAliasManager::_build_user_spec(entry: {entry})")

        name = str(entry.get("name", "")).strip()
        if not name:
            raise ValueError("users[] entry must include a non-empty 'name'")

        try:
            pw = pwd.getpwnam(name)
        except KeyError:
            raise ValueError(f"User does not exist: {name!r}")

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

        aliases = self._validate_aliases(aliases_raw)
        functions = self._validate_functions(funcs_raw)

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

    def _atomic_write_text(
        self,
        path: str,
        content: str,
        mode: int,
        uid: int,
        gid: int,
        check_mode: bool,
    ) -> None:
        """Write file atomically with desired ownership and permissions."""
        self.module.log(
            f"BashAliasManager::_atomic_write_text(path: {path}, content, mode: {mode}, uid: {uid}, gid: {gid}, check_mode: {check_mode})"
        )

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

    def _render_aliases(self, aliases: Sequence[AliasSpec]) -> str:
        """Render deterministic .bash_aliases content."""
        self.module.log(f"BashAliasManager::_render_aliases(aliases: {aliases})")

        lines: List[str] = [
            "# Managed by Ansible module bash_alias_manage. Do not edit manually.",
            "",
        ]
        for a in aliases:
            if a.comment:
                lines.append(f"# {a.comment}")
            lines.append(f"alias {a.name}={self._bash_single_quote(a.command)}")
        lines.append("")
        return "\n".join(lines)

    def _render_functions(self, functions: Sequence[FunctionSpec]) -> str:
        """Render deterministic .bash_functions content."""
        self.module.log(f"BashAliasManager::_render_functions(functions: {functions})")

        lines: List[str] = [
            "# Managed by Ansible module bash_alias_manage. Do not edit manually.",
            "",
        ]
        for f in functions:
            if f.comment:
                lines.append(f"# {f.comment}")
            lines.append(f"{f.name}() {{")
            body = f.content.strip("\n")
            for bline in body.splitlines():
                lines.append(f"  {bline.rstrip()}")
            lines.append("}")
            lines.append("")
        return "\n".join(lines)

    def _bash_single_quote(self, s: str) -> str:
        """
        Quote a string for bash using single quotes, escaping embedded single quotes.

        Example: abc'def -> 'abc'"'"'def'
        """
        return "'" + s.replace("'", "'\"'\"'") + "'"

    def _validate_filename(self, name: str, field: str) -> str:
        """Validate that filenames are simple basenames (no path separators)."""
        n = str(name).strip()
        if not n:
            raise ValueError(f"{field} must not be empty")
        if "/" in n or "\x00" in n:
            raise ValueError(f"{field} must be a basename without '/' or NUL: {n!r}")
        return n

    def _read_text(self, path: str) -> Optional[str]:
        """Read a text file; return None if missing/unreadable."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
                return f.read()
        except OSError:
            return None

    def _remove_file(self, path: str, check_mode: bool) -> None:
        """Remove a file if it exists."""
        if check_mode:
            return
        try:
            os.unlink(path)
        except FileNotFoundError:
            return

    def _remove_bashrc_block(self, existing: str) -> Tuple[bool, str]:
        """Remove marker block from bashrc content."""
        begin = existing.find(_MARKER_BEGIN)
        end = existing.find(_MARKER_END)
        if begin == -1 or end == -1 or end <= begin:
            return False, existing

        pre = existing[:begin].rstrip("\n")
        post = existing[end + len(_MARKER_END) :].lstrip("\n")
        new_content = (pre + "\n" + post).strip("\n") + "\n"
        if new_content == existing:
            return False, existing
        return True, new_content


# --------------------------------------------------------------------------------------------------


def main() -> None:
    """Ansible module entrypoint."""
    argument_spec = dict(
        users=dict(type="list", elements="dict", required=True),
        common_aliases=dict(type="list", elements="dict", required=False, default=[]),
        common_functions=dict(type="list", elements="dict", required=False, default=[]),
        state=dict(
            type="str", required=False, default="present", choices=["present", "absent"]
        ),
        backup=dict(type="bool", required=False, default=True),
        fail_on_error=dict(type="bool", required=False, default=True),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    mgr = BashAliasManager(module)
    result = mgr.run()

    module.log(msg=f"= result : '{result}'")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
