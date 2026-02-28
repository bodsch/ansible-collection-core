"""
binary_deploy_impl.py

Idempotent deployment helper for versioned binaries with activation symlinks.

This module is intended to be used from Ansible modules (and optionally an action plugin)
to deploy one or multiple binaries into a versioned installation directory and activate
them via symlinks (e.g. /usr/bin/<name> -> <install_dir>/<name>).

Key features:
- Optional copy from a remote staging directory (remote -> remote) with atomic replacement.
- Permission and ownership enforcement (mode/owner/group).
- Optional Linux file capabilities via getcap/setcap with normalized, idempotent comparison.
- Activation detection based on symlink target.

Public API:
- BinaryDeploy.run(): reads AnsibleModule params and returns module JSON via exit_json/fail_json.
"""

from __future__ import annotations

import grp
import hashlib
import os
import pwd
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ansible.module_utils.basic import AnsibleModule

_CHUNK_SIZE = 1024 * 1024
_CAP_ENTRY_RE = re.compile(r"^(cap_[a-z0-9_]+)([=+])([a-z]+)$", re.IGNORECASE)


@dataclass(frozen=True)
class BinaryItem:
    """A single deployable binary with optional activation name and capability."""

    name: str
    src: str
    link_name: str
    capability: Optional[str]


class _PathOps:
    """Filesystem helper methods used by the deployment logic."""

    @staticmethod
    def sha256_file(path: str) -> str:
        """
        Calculate the SHA-256 checksum of a file.

        Args:
            path: Path to the file.

        Returns:
            Hex-encoded SHA-256 digest.
        """
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def files_equal(src: str, dst: str) -> bool:
        """
        Compare two files for equality by size and SHA-256 checksum.

        This is used to decide whether a copy is required.

        Args:
            src: Source file path.
            dst: Destination file path.

        Returns:
            True if both files exist and are byte-identical, otherwise False.
        """
        if os.path.abspath(src) == os.path.abspath(dst):
            return True
        try:
            if os.path.samefile(src, dst):
                return True
        except FileNotFoundError:
            return False
        except OSError:
            # samefile may fail on some filesystems; fall back to hashing
            pass

        try:
            s1 = os.stat(src)
            s2 = os.stat(dst)
        except FileNotFoundError:
            return False

        if s1.st_size != s2.st_size:
            return False

        # Hashing is the expensive path; size match is a cheap early filter.
        return _PathOps.sha256_file(src) == _PathOps.sha256_file(dst)

    @staticmethod
    def ensure_dir(path: str) -> bool:
        """
        Ensure a directory exists.

        Args:
            path: Directory path.

        Returns:
            True if the directory was created, otherwise False.
        """
        if os.path.isdir(path):
            return False
        os.makedirs(path, exist_ok=True)
        return True

    @staticmethod
    def safe_rmtree(path: str) -> None:
        """
        Remove a directory tree with a minimal safety guard.

        Args:
            path: Directory to remove.

        Raises:
            ValueError: If the path is empty or points to '/'.
        """
        if not path or os.path.abspath(path) in ("/",):
            raise ValueError(f"Refusing to remove unsafe path: {path}")
        shutil.rmtree(path)

    @staticmethod
    def is_symlink_to(link_path: str, target_path: str) -> bool:
        """
        Check whether link_path is a symlink pointing to target_path.

        Args:
            link_path: Symlink location.
            target_path: Expected symlink target.

        Returns:
            True if link_path is a symlink to target_path, otherwise False.
        """
        try:
            if not os.path.islink(link_path):
                return False
            current = os.readlink(link_path)
        except OSError:
            return False

        # Normalize relative symlinks to absolute for comparison.
        if not os.path.isabs(current):
            current = os.path.abspath(os.path.join(os.path.dirname(link_path), current))

        return os.path.abspath(current) == os.path.abspath(target_path)

    @staticmethod
    def ensure_symlink(link_path: str, target_path: str) -> bool:
        """
        Ensure link_path is a symlink to target_path.

        Args:
            link_path: Symlink location.
            target_path: Symlink target.

        Returns:
            True if the symlink was created/updated, otherwise False.
        """
        if _PathOps.is_symlink_to(link_path, target_path):
            return False

        # Replace existing file/link.
        try:
            os.lstat(link_path)
            os.unlink(link_path)
        except FileNotFoundError:
            pass

        os.symlink(target_path, link_path)
        return True

    @staticmethod
    def atomic_copy(src: str, dst: str) -> None:
        """
        Copy a file to dst atomically (write to temp file and rename).

        Args:
            src: Source file path.
            dst: Destination file path.
        """
        dst_dir = os.path.dirname(dst)
        _PathOps.ensure_dir(dst_dir)

        fd, tmp_path = tempfile.mkstemp(prefix=".ansible-binary-", dir=dst_dir)
        os.close(fd)
        try:
            shutil.copyfile(src, tmp_path)
            os.replace(tmp_path, dst)
        finally:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


class _Identity:
    """User/group resolution helpers."""

    @staticmethod
    def resolve_uid(owner: Optional[str]) -> Optional[int]:
        """
        Resolve a user name or uid string to a numeric uid.

        Args:
            owner: User name or numeric uid as string.

        Returns:
            Numeric uid, or None if owner is None.
        """
        if owner is None:
            return None
        if owner.isdigit():
            return int(owner)
        return pwd.getpwnam(owner).pw_uid

    @staticmethod
    def resolve_gid(group: Optional[str]) -> Optional[int]:
        """
        Resolve a group name or gid string to a numeric gid.

        Args:
            group: Group name or numeric gid as string.

        Returns:
            Numeric gid, or None if group is None.
        """
        if group is None:
            return None
        if group.isdigit():
            return int(group)
        return grp.getgrnam(group).gr_gid


@dataclass(frozen=True)
class _CapsValue:
    """Normalized representation of Linux file capabilities."""

    value: str

    @staticmethod
    def normalize(raw: str) -> "_CapsValue":
        """
        Normalize capability strings so that setcap-style and getcap-style
        representations compare equal.

        Examples:
          - "cap_net_raw+ep" -> "cap_net_raw=ep"
          - "cap_net_raw=pe" -> "cap_net_raw=ep"
          - "cap_a+e, cap_b=ip" -> "cap_a=e,cap_b=ip"
        """
        s = (raw or "").strip()
        if not s:
            return _CapsValue("")

        entries: List[str] = []
        for part in s.split(","):
            p = part.strip()
            if not p:
                continue

            # Remove internal whitespace.
            p = " ".join(p.split())

            m = _CAP_ENTRY_RE.match(p)
            if not m:
                # Unknown format: keep as-is (but trimmed).
                entries.append(p)
                continue

            cap_name, _, flags = m.group(1), m.group(2), m.group(3)
            flags_norm = "".join(sorted(flags))
            # Canonical operator is '=' (getcap output style).
            entries.append(f"{cap_name}={flags_norm}")

        entries.sort()
        return _CapsValue(",".join(entries))


class _Caps:
    """
    Linux file capabilities helper with idempotent detection via getcap/setcap.

    The helper normalizes both desired and current values to avoid false positives,
    e.g. comparing 'cap_net_raw+ep' (setcap style) and 'cap_net_raw=ep' (getcap style).
    """

    def __init__(self, module: AnsibleModule) -> None:
        self._module = module

    def _parse_getcap_output(self, path: str, out: str) -> _CapsValue:
        """
        Parse getcap output for a single path.

        Supported formats:
          - "/path cap_net_raw=ep"
          - "/path = cap_net_raw=ep"
          - "/path cap_net_raw+ep" (rare, but normalize handles it)
        """
        text = (out or "").strip()
        if not text:
            return _CapsValue("")

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Example lines:
            #   /usr/bin/ping = cap_net_raw+ep
            #   /usr/bin/ping cap_net_raw=ep
            if line.startswith(path):
                _path_len = len(path)
                rest = line[_path_len:].strip()

                # Strip optional leading '=' or split form.
                if rest.startswith("="):
                    rest = rest[1:].strip()

                tokens = rest.split()
                if tokens and tokens[0] == "=":
                    rest = " ".join(tokens[1:]).strip()

                return _CapsValue.normalize(rest)

        # Fallback: if getcap returned a single line but path formatting differs.
        first = text.splitlines()[0].strip()
        tokens = first.split()
        if len(tokens) >= 2:
            if tokens[1] == "=" and len(tokens) >= 3:
                return _CapsValue.normalize(" ".join(tokens[2:]))
            return _CapsValue.normalize(" ".join(tokens[1:]))

        return _CapsValue("")

    def get_current(self, path: str) -> Optional[_CapsValue]:
        """
        Get the current capability set for a file.

        Returns:
            - _CapsValue("") for no capabilities
            - _CapsValue("cap_xxx=ep") for set capabilities
            - None if getcap is missing (cannot do idempotent checks)
        """
        rc, out, err = self._module.run_command(["getcap", path])
        if rc == 127:
            return None
        if rc != 0:
            msg = (err or "").strip()
            # No capabilities can be signaled via non-zero return with empty output.
            if msg and "No such file" in msg:
                self._module.fail_json(msg=f"getcap failed: {msg}", path=path)
            return _CapsValue("")
        return self._parse_getcap_output(path, out)

    def ensure(self, path: str, desired: str) -> bool:
        """
        Ensure the desired capability is present on 'path'.

        Args:
            path: File path.
            desired: Capability string (setcap/getcap style), e.g. "cap_net_raw+ep".

        Returns:
            True if a change was applied, otherwise False.

        Raises:
            AnsibleModule.fail_json on errors or if getcap is missing.
        """
        desired_norm = _CapsValue.normalize(desired)
        current = self.get_current(path)

        if current is None:
            self._module.fail_json(
                msg="getcap is required for idempotent capability management",
                hint="Install libcap tools (e.g. Debian/Ubuntu: 'libcap2-bin')",
                path=path,
                desired=desired_norm.value,
            )

        if current.value == desired_norm.value:
            return False

        # setcap accepts both '+ep' and '=ep', but we pass canonical '=...'.
        rc, out, err = self._module.run_command(["setcap", desired_norm.value, path])
        if rc != 0:
            msg = (err or out or "").strip() or "setcap failed"
            self._module.fail_json(msg=msg, path=path, capability=desired_norm.value)

        verified = self.get_current(path)
        if verified is None or verified.value != desired_norm.value:
            self._module.fail_json(
                msg="capability verification failed after setcap",
                path=path,
                desired=desired_norm.value,
                current=(verified.value if verified else None),
            )

        return True


class BinaryDeploy:
    """
    Deployment engine used by Ansible modules.

    The instance consumes module parameters, plans whether an update is necessary,
    and then applies changes idempotently:
    - copy (optional)
    - permissions and ownership
    - capabilities (optional)
    - activation symlink
    """

    def __init__(self, module: AnsibleModule) -> None:
        self._module = module
        self._module.log("BinaryDeploy::__init__()")
        self._caps = _Caps(module)

    @staticmethod
    def _parse_mode(mode: Any) -> int:
        """
        Parse a file mode parameter into an int.

        Args:
            mode: Octal mode as string (e.g. "0755") or int.

        Returns:
            Parsed mode as int.
        """
        if isinstance(mode, int):
            return mode
        s = str(mode).strip()
        return int(s, 8)

    def _resolve_uid_gid(
        self, owner: Optional[str], group: Optional[str]
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Resolve owner/group into numeric uid/gid.

        Raises:
            ValueError: If the user or group does not exist.
        """
        try:
            return _Identity.resolve_uid(owner), _Identity.resolve_gid(group)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

    def _parse_items(self, raw: List[Dict[str, Any]]) -> List[BinaryItem]:
        """
        Parse module 'items' parameter into BinaryItem objects.

        Each raw item supports:
          - name (required)
          - src (optional, defaults to name)
          - link_name (optional, defaults to name)
          - capability (optional)
        """
        self._module.log(f"BinaryDeploy::_parse_items(raw: {raw})")

        items: List[BinaryItem] = []
        for it in raw:
            name = str(it["name"])
            src = str(it.get("src") or name)
            link_name = str(it.get("link_name") or name)
            cap = it.get("capability")
            items.append(
                BinaryItem(
                    name=name,
                    src=src,
                    link_name=link_name,
                    capability=str(cap) if cap else None,
                )
            )
        return items

    def _plan(
        self,
        *,
        install_dir: str,
        link_dir: str,
        src_dir: Optional[str],
        do_copy: bool,
        items: List[BinaryItem],
        activation_name: str,
        owner: Optional[str],
        group: Optional[str],
        mode: int,
    ) -> Tuple[bool, bool, Dict[str, Dict[str, bool]]]:
        """
        Build an idempotent plan for all items.

        Returns:
            Tuple of:
              - activated: whether the activation symlink points into install_dir
              - needs_update: whether any operation would be required
              - per_item_plan: dict(item.name -> {copy, perms, cap, link})
        """
        self._module.log(
            "BinaryDeploy::_plan("
            f"install_dir: {install_dir}, link_dir: {link_dir}, src_dir: {src_dir}, "
            f"do_copy: {do_copy}, items: {items}, activation_name: {activation_name}, "
            f"owner: {owner}, group: {group}, mode: {mode})"
        )

        activation = next(
            (
                i
                for i in items
                if i.name == activation_name or i.link_name == activation_name
            ),
            items[0],
        )
        activation_target = os.path.join(install_dir, activation.name)
        activation_link = os.path.join(link_dir, activation.link_name)
        activated = os.path.isfile(activation_target) and _PathOps.is_symlink_to(
            activation_link, activation_target
        )

        try:
            uid, gid = self._resolve_uid_gid(owner, group)
        except ValueError as exc:
            self._module.fail_json(msg=str(exc))

        needs_update = False
        per_item: Dict[str, Dict[str, bool]] = {}

        for item in items:
            dst = os.path.join(install_dir, item.name)
            lnk = os.path.join(link_dir, item.link_name)
            src = os.path.join(src_dir, item.src) if (do_copy and src_dir) else None

            item_plan: Dict[str, bool] = {
                "copy": False,
                "perms": False,
                "cap": False,
                "link": False,
            }

            if do_copy:
                if src is None:
                    self._module.fail_json(
                        msg="src_dir is required when copy=true", item=item.name
                    )
                if not os.path.isfile(src):
                    self._module.fail_json(
                        msg="source binary missing on remote host",
                        src=src,
                        item=item.name,
                    )
                if not os.path.exists(dst) or not _PathOps.files_equal(src, dst):
                    item_plan["copy"] = True

            # perms/ownership (if file missing, perms will be set later)
            try:
                st = os.stat(dst)
                if (st.st_mode & 0o7777) != mode:
                    item_plan["perms"] = True
                if uid is not None and st.st_uid != uid:
                    item_plan["perms"] = True
                if gid is not None and st.st_gid != gid:
                    item_plan["perms"] = True
            except FileNotFoundError:
                item_plan["perms"] = True

            if item.capability:
                desired_norm = _CapsValue.normalize(item.capability)

                if not os.path.exists(dst):
                    item_plan["cap"] = True
                else:
                    current = self._caps.get_current(dst)
                    if current is None:
                        # getcap missing -> cannot validate, apply will fail in ensure().
                        item_plan["cap"] = True
                    elif current.value != desired_norm.value:
                        item_plan["cap"] = True

            if not _PathOps.is_symlink_to(lnk, dst):
                item_plan["link"] = True

            if any(item_plan.values()):
                needs_update = True
            per_item[item.name] = item_plan

        return activated, needs_update, per_item

    def run(self) -> None:
        """
        Execute the deployment based on module parameters.

        Module parameters (expected):
            install_dir (str), link_dir (str), src_dir (optional str), copy (bool),
            items (list[dict]), activation_name (optional str),
            owner (optional str), group (optional str), mode (str),
            cleanup_on_failure (bool), check_only (bool).
        """
        self._module.log("BinaryDeploy::run()")

        p = self._module.params

        install_dir: str = p["install_dir"]
        link_dir: str = p["link_dir"]
        src_dir: Optional[str] = p.get("src_dir")
        do_copy: bool = bool(p["copy"])
        cleanup_on_failure: bool = bool(p["cleanup_on_failure"])
        activation_name: str = str(p.get("activation_name") or "")

        owner: Optional[str] = p.get("owner")
        group: Optional[str] = p.get("group")
        mode_int = self._parse_mode(p["mode"])

        items = self._parse_items(p["items"])
        if not items:
            self._module.fail_json(msg="items must not be empty")

        if not activation_name:
            activation_name = items[0].name

        check_only: bool = bool(p["check_only"]) or bool(self._module.check_mode)

        activated, needs_update, plan = self._plan(
            install_dir=install_dir,
            link_dir=link_dir,
            src_dir=src_dir,
            do_copy=do_copy,
            items=items,
            activation_name=activation_name,
            owner=owner,
            group=group,
            mode=mode_int,
        )

        if check_only:
            self._module.exit_json(
                changed=False, activated=activated, needs_update=needs_update, plan=plan
            )

        changed = False
        details: Dict[str, Dict[str, bool]] = {}

        try:
            if _PathOps.ensure_dir(install_dir):
                changed = True

            uid, gid = self._resolve_uid_gid(owner, group)

            for item in items:
                src = os.path.join(src_dir, item.src) if (do_copy and src_dir) else None
                dst = os.path.join(install_dir, item.name)
                lnk = os.path.join(link_dir, item.link_name)

                item_changed: Dict[str, bool] = {
                    "copied": False,
                    "perms": False,
                    "cap": False,
                    "link": False,
                }

                if do_copy:
                    if src is None:
                        self._module.fail_json(
                            msg="src_dir is required when copy=true", item=item.name
                        )
                    if not os.path.exists(dst) or not _PathOps.files_equal(src, dst):
                        _PathOps.atomic_copy(src, dst)
                        item_changed["copied"] = True
                        changed = True

                if not os.path.exists(dst):
                    self._module.fail_json(
                        msg="destination binary missing in install_dir",
                        dst=dst,
                        hint="In controller-local mode this indicates the transfer/copy stage did not create the file.",
                        item=item.name,
                    )

                st = os.stat(dst)

                if (st.st_mode & 0o7777) != mode_int:
                    os.chmod(dst, mode_int)
                    item_changed["perms"] = True
                    changed = True

                if uid is not None or gid is not None:
                    new_uid = uid if uid is not None else st.st_uid
                    new_gid = gid if gid is not None else st.st_gid
                    if new_uid != st.st_uid or new_gid != st.st_gid:
                        os.chown(dst, new_uid, new_gid)
                        item_changed["perms"] = True
                        changed = True

                if item.capability:
                    if self._caps.ensure(dst, item.capability):
                        item_changed["cap"] = True
                        changed = True

                if _PathOps.ensure_symlink(lnk, dst):
                    item_changed["link"] = True
                    changed = True

                details[item.name] = item_changed

        except Exception as exc:
            if cleanup_on_failure:
                try:
                    _PathOps.safe_rmtree(install_dir)
                except Exception:
                    pass
            self._module.fail_json(msg=str(exc), exception=repr(exc))

        activation = next(
            (
                i
                for i in items
                if i.name == activation_name or i.link_name == activation_name
            ),
            items[0],
        )
        activation_target = os.path.join(install_dir, activation.name)
        activation_link = os.path.join(link_dir, activation.link_name)
        activated = os.path.isfile(activation_target) and _PathOps.is_symlink_to(
            activation_link, activation_target
        )

        self._module.exit_json(
            changed=changed, activated=activated, needs_update=False, details=details
        )
