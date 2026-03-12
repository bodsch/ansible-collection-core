#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to manage bash aliases and functions for multiple users efficiently.

This module validates users and their home directories, then writes deterministic
bash alias/function files into each user's home directory. Optionally it ensures
the user's .bashrc sources these files by managing a dedicated marker block.

Design goals:
- Single module invocation per host (avoid Ansible task loops).
- Idempotent file rendering based on full desired content.
- Safe file updates using atomic replace.
- Optional backups for changed/removed files.
- No subprocess usage.
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
short_description: Manage bash aliases and functions for many users (idempotent, fast)
version_added: "1.0.0"

description:
  - Validates users and their home directories.
  - Writes deterministic alias and function files into each user's home directory.
  - Optionally ensures C(.bashrc) sources these files via a managed marker block.
  - Designed to avoid Ansible task loops by handling all users in a single module run.

options:
  users:
    description:
      - List of user specifications.
      - Each item defines aliases/functions and optional filenames.
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
            description: Alias name.
            required: true
            type: str
          command:
            description: Alias command.
            required: true
            type: str
          comment:
            description: Optional comment line preceding the alias.
            required: false
            type: str
      functions:
        description: List of bash function definitions for this user.
        required: false
        type: list
        elements: dict
        suboptions:
          name:
            description: Function name.
            required: true
            type: str
          content:
            description: Function body content (multi-line allowed).
            required: true
            type: str
          comment:
            description: Optional comment line preceding the function.
            required: false
            type: str
      manage_bashrc:
        description: Whether to manage a marker block in user's .bashrc to source managed files.
        required: false
        type: bool
        default: true
      aliases_filename:
        description: Alias filename within the user's home directory.
        required: false
        type: str
        default: ".bash_aliases"
      functions_filename:
        description: Functions filename within the user's home directory.
        required: false
        type: str
        default: ".bash_functions"
      bashrc_filename:
        description: Bashrc filename within the user's home directory.
        required: false
        type: str
        default: ".bashrc"
  common_aliases:
    description: Aliases applied to every user (prepended before user-specific aliases).
    required: false
    type: list
    default: []
    elements: dict
  common_functions:
    description: Functions applied to every user (prepended before user-specific functions).
    required: false
    type: list
    default: []
    elements: dict
  state:
    description:
      - Whether the managed files and bashrc block should exist.
      - C(absent) removes the managed files and the marker block from .bashrc.
    required: false
    type: str
    default: present
    choices: [present, absent]
  backup:
    description: Create backups of files before changing or deleting them.
    required: false
    type: bool
    default: true
  allow_unsupported:
    description:
      - By default the module fails on unsupported distributions.
      - Set to true to run on other distributions as well.
    required: false
    type: bool
    default: false
author:
  - "Your Name"
"""

EXAMPLES = r"""
- name: Manage bash aliases/functions for many users in one task
  become: true
  bodsch.core.bash_aliases:
    state: present
    backup: true
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
  bodsch.core.bash_aliases:
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
results:
  description: Per-user summary.
  returned: always
  type: list
  elements: dict
  sample:
    - user: alice
      changed: true
      files:
        - path: /home/alice/.bash_aliases
          action: updated
          backup: /home/alice/.bash_aliases.12345.2026-03-12@12:00~
        - path: /home/alice/.bashrc
          action: updated
          backup: /home/alice/.bashrc.12345.2026-03-12@12:00~
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


def _read_os_release() -> Dict[str, str]:
    """Read /etc/os-release into a key/value mapping."""
    data: Dict[str, str] = {}
    path = "/etc/os-release"
    if not os.path.exists(path):
        return data
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                data[k.strip()] = v
    except OSError:
        return data
    return data


def _is_supported_distribution(osr: Mapping[str, str]) -> bool:
    """Return True if distribution is supported (Arch or Debian-like)."""
    distro_id = (osr.get("ID") or "").lower()
    distro_like = (osr.get("ID_LIKE") or "").lower()

    if distro_id == "arch":
        return True
    if distro_id in {"debian", "ubuntu", "linuxmint", "pop"}:
        return True
    if "debian" in distro_like:
        return True
    return False


def _bash_single_quote(s: str) -> str:
    """
    Quote a string for bash using single quotes, escaping embedded single quotes.

    Example: abc'def -> 'abc'"'"'def'
    """
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _validate_aliases(raw: Sequence[Mapping[str, Any]]) -> Tuple[AliasSpec, ...]:
    """Validate and normalize alias specs."""
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


def _validate_functions(raw: Sequence[Mapping[str, Any]]) -> Tuple[FunctionSpec, ...]:
    """Validate and normalize function specs."""
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


def _render_aliases(aliases: Sequence[AliasSpec]) -> str:
    """Render deterministic .bash_aliases content."""
    lines: List[str] = [
        "# Managed by Ansible module bash_alias_manage. Do not edit manually.",
        "",
    ]
    for a in aliases:
        if a.comment:
            lines.append(f"# {a.comment}")
        lines.append(f"alias {a.name}={_bash_single_quote(a.command)}")
    lines.append("")
    return "\n".join(lines)


def _render_functions(functions: Sequence[FunctionSpec]) -> str:
    """Render deterministic .bash_functions content."""
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


def _read_text(path: str) -> Optional[str]:
    """Read a text file; return None if missing."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
            return f.read()
    except OSError:
        return None


def _atomic_write_text(
    path: str,
    content: str,
    mode: int,
    uid: int,
    gid: int,
    check_mode: bool,
) -> None:
    """Write file atomically with desired ownership and permissions."""
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


def _remove_file(path: str, check_mode: bool) -> None:
    """Remove a file if it exists."""
    if check_mode:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        return


def _ensure_bashrc_block(
    bashrc_path: str,
    block: str,
    mode: int,
    uid: int,
    gid: int,
    check_mode: bool,
    current: Optional[str],
) -> Tuple[bool, str]:
    """
    Ensure the marker block exists and matches exactly.

    Returns (changed, new_content).
    """
    existing = current if current is not None else ""
    if existing == "":
        new_content = block if block.endswith("\n") else (block + "\n")
        return True, new_content

    begin = existing.find(_MARKER_BEGIN)
    end = existing.find(_MARKER_END)

    if begin != -1 and end != -1 and end > begin:
        # Replace whole region (from begin line start to end line end).
        # Normalize to include full marker lines.
        pre = existing[:begin].rstrip("\n")
        post = existing[end + len(_MARKER_END):].lstrip("\n")
        new_content = pre + "\n" + block.strip("\n") + "\n" + post
    else:
        # Append to end.
        new_content = existing.rstrip("\n") + "\n\n" + block.strip("\n") + "\n"

    if new_content == existing:
        return False, existing

    if not check_mode:
        _atomic_write_text(
            bashrc_path, new_content, mode=mode, uid=uid, gid=gid, check_mode=False
        )
    return True, new_content


def _remove_bashrc_block(existing: str) -> Tuple[bool, str]:
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


class BashAliasManager:
    """Core implementation that applies desired state for all configured users."""

    def __init__(self, module: AnsibleModule) -> None:
        self._m = module
        self._backup = bool(module.params["backup"])
        self._check = bool(module.check_mode)

    def apply(
        self,
        state: str,
        users: Sequence[UserSpec],
        common_aliases: Tuple[AliasSpec, ...],
        common_functions: Tuple[FunctionSpec, ...],
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Apply state for all users and return (changed, results)."""
        overall_changed = False
        results: List[Dict[str, Any]] = []

        for u in users:
            user_changed, files = self._apply_user(
                state, u, common_aliases, common_functions
            )
            overall_changed = overall_changed or user_changed
            results.append(
                {
                    "user": u.name,
                    "changed": user_changed,
                    "files": [fc.__dict__ for fc in files],
                }
            )

        return overall_changed, results

    def _apply_user(
        self,
        state: str,
        user: UserSpec,
        common_aliases: Tuple[AliasSpec, ...],
        common_functions: Tuple[FunctionSpec, ...],
    ) -> Tuple[bool, List[FileChange]]:
        """Apply desired state for a single user."""
        changed = False
        files: List[FileChange] = []

        aliases_path = os.path.join(user.home, user.aliases_filename)
        functions_path = os.path.join(user.home, user.functions_filename)
        bashrc_path = os.path.join(user.home, user.bashrc_filename)

        if state == "present":
            # Render deterministic content
            aliases_content = _render_aliases(
                tuple(common_aliases) + tuple(user.aliases)
            )
            functions_content = _render_functions(
                tuple(common_functions) + tuple(user.functions)
            )

            changed |= self._ensure_file(aliases_path, aliases_content, user, files)
            changed |= self._ensure_file(functions_path, functions_content, user, files)

            if user.manage_bashrc:
                block = self._bashrc_block(aliases_path, functions_path)
                bashrc_current = _read_text(bashrc_path)
                if bashrc_current is None:
                    # Create new .bashrc containing only the block (safe minimal behavior)
                    if self._backup and os.path.exists(bashrc_path):
                        bkp = self._m.backup_local(bashrc_path)
                    else:
                        bkp = None
                    if bashrc_current != block + "\n":
                        if not self._check:
                            _atomic_write_text(
                                bashrc_path,
                                block + "\n",
                                mode=0o644,
                                uid=user.uid,
                                gid=user.gid,
                                check_mode=False,
                            )
                        changed = True
                        files.append(
                            FileChange(path=bashrc_path, action="created", backup=bkp)
                        )
                    else:
                        files.append(FileChange(path=bashrc_path, action="unchanged"))
                else:
                    if self._needs_change_bashrc(bashrc_current, block):
                        bkp = self._maybe_backup(bashrc_path)
                        if not self._check:
                            _atomic_write_text(
                                bashrc_path,
                                self._merge_bashrc(bashrc_current, block),
                                mode=0o644,
                                uid=user.uid,
                                gid=user.gid,
                                check_mode=False,
                            )
                        changed = True
                        files.append(
                            FileChange(path=bashrc_path, action="updated", backup=bkp)
                        )
                    else:
                        files.append(FileChange(path=bashrc_path, action="unchanged"))

        elif state == "absent":
            # Remove managed files
            changed |= self._remove_if_exists(aliases_path, files)
            changed |= self._remove_if_exists(functions_path, files)

            # Remove marker block from .bashrc
            bashrc_current = _read_text(bashrc_path)
            if bashrc_current is not None:
                needs, new_content = _remove_bashrc_block(bashrc_current)
                if needs:
                    bkp = self._maybe_backup(bashrc_path)
                    if not self._check:
                        _atomic_write_text(
                            bashrc_path,
                            new_content,
                            mode=0o644,
                            uid=user.uid,
                            gid=user.gid,
                            check_mode=False,
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
        """Create a backup of path if enabled and file exists."""
        if not self._backup:
            return None
        if not os.path.exists(path):
            return None
        return self._m.backup_local(path)

    def _ensure_file(
        self, path: str, content: str, user: UserSpec, files: List[FileChange]
    ) -> bool:
        """Ensure file exists with exact content."""
        current = _read_text(path)
        desired = content if content.endswith("\n") else (content + "\n")

        if current is None:
            bkp = self._maybe_backup(path)
            _atomic_write_text(
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
            _atomic_write_text(
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
        if not os.path.exists(path):
            files.append(FileChange(path=path, action="unchanged"))
            return False
        bkp = self._maybe_backup(path)
        _remove_file(path, check_mode=self._check)
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

    @staticmethod
    def _needs_change_bashrc(existing: str, block: str) -> bool:
        """Check if bashrc needs to be modified to contain the desired block."""
        begin = existing.find(_MARKER_BEGIN)
        end = existing.find(_MARKER_END)
        desired = block.strip("\n")

        if begin != -1 and end != -1 and end > begin:
            current_block = existing[begin : end + len(_MARKER_END)].strip("\n")
            return current_block != desired

        # Not present -> needs append
        return True

    @staticmethod
    def _merge_bashrc(existing: str, block: str) -> str:
        """Merge/replace marker block into bashrc content."""
        begin = existing.find(_MARKER_BEGIN)
        end = existing.find(_MARKER_END)
        blk = block.strip("\n")

        if begin != -1 and end != -1 and end > begin:
            pre = existing[:begin].rstrip("\n")
            post = existing[end + len(_MARKER_END) :].lstrip("\n")
            merged = pre + "\n" + blk + "\n" + post
        else:
            merged = existing.rstrip("\n") + "\n\n" + blk + "\n"

        if not merged.endswith("\n"):
            merged += "\n"
        return merged


def _build_user_specs(
    module: AnsibleModule,
    common_aliases: Tuple[AliasSpec, ...],
    common_functions: Tuple[FunctionSpec, ...],
) -> List[UserSpec]:
    """Validate module params and build UserSpec objects."""
    users_param: Sequence[Mapping[str, Any]] = module.params["users"]

    user_specs: List[UserSpec] = []
    for u in users_param:
        name = str(u.get("name", "")).strip()
        if not name:
            raise ValueError("Each users[] entry must include a non-empty 'name'.")

        pw = pwd.getpwnam(name)  # raises KeyError if user does not exist
        home = pw.pw_dir
        if not home or not os.path.isabs(home) or not os.path.isdir(home):
            raise ValueError(
                f"User {name!r} has invalid or missing home directory: {home!r}"
            )

        manage_bashrc = bool(u.get("manage_bashrc", True))
        aliases_filename = str(u.get("aliases_filename", ".bash_aliases"))
        functions_filename = str(u.get("functions_filename", ".bash_functions"))
        bashrc_filename = str(u.get("bashrc_filename", ".bashrc"))

        aliases_raw = u.get("aliases", []) or []
        funcs_raw = u.get("functions", []) or []

        aliases = _validate_aliases(aliases_raw)
        functions = _validate_functions(funcs_raw)

        # Note: common_* are applied during render; keep user-only here.
        user_specs.append(
            UserSpec(
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
        )

    return user_specs


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
        allow_unsupported=dict(type="bool", required=False, default=False),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    osr = _read_os_release()
    if not module.params["allow_unsupported"] and not _is_supported_distribution(osr):
        module.fail_json(
            msg="Unsupported distribution for bash_alias_manage (supported: Arch, Debian/Ubuntu). "
            "Set allow_unsupported=true to override.",
            os_release=osr,
        )

    try:
        common_aliases = _validate_aliases(module.params["common_aliases"] or [])
        common_functions = _validate_functions(module.params["common_functions"] or [])
        users = _build_user_specs(module, common_aliases, common_functions)

        mgr = BashAliasManager(module)
        changed, results = mgr.apply(
            state=str(module.params["state"]),
            users=users,
            common_aliases=common_aliases,
            common_functions=common_functions,
        )
        module.exit_json(changed=changed, results=results, os_release=osr)
    except KeyError as e:
        module.fail_json(msg=f"User does not exist: {e}")
    except ValueError as e:
        module.fail_json(msg=str(e))
    except Exception as e:
        module.fail_json(msg=f"Unhandled error: {e}")


if __name__ == "__main__":
    main()
