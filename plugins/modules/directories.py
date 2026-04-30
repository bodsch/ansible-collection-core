#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Ansible module: bodsch.core.directories
========================================

Provides idempotent, batch creation of directory trees on the target system.

Unlike the built-in ``ansible.builtin.file`` module combined with a loop, this
module accepts a list of path specifications and processes all of them in a
single Python invocation on the target host, which eliminates the per-task SSH
round-trip overhead for each individual directory.

Key behaviours
--------------
- **Absolute paths** (starting with ``/``) are created exactly as specified,
  regardless of the ``base_path`` parameter.
- **Relative paths** are resolved against ``base_path``.
- Each path entry may override the global ``owner``, ``group``, and ``mode``
  defaults.  Any attribute not defined per path falls back to the corresponding
  module-level default.
- All filesystem operations are **idempotent**: existing directories with the
  correct ownership and permissions are left untouched and do not trigger a
  ``changed`` state.
- Full **check-mode** support: no writes are performed; expected changes are
  reported only.

Module parameters
-----------------
See the ``DOCUMENTATION`` string below for the complete Ansible-style
argument specification.

Return values
-------------
See the ``RETURN`` string below.  The ``directories`` list mirrors the input
``paths`` list and carries the resolved path plus the outcome for every entry.

Dependencies
------------
- Python standard library: ``grp``, ``os``, ``pwd``, ``stat``
- Ansible: ``ansible.module_utils.basic.AnsibleModule``

:author: Bodo Schulz <me+ansible@bodsch.me>
:license: Apache-2.0
:version_added: 1.13.0
"""

# (c) 2025-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import grp
import os
import pwd
import stat as stat_module
from typing import Any, Dict, List, Optional

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: directories
version_added: "1.13.0"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Create a tree of directories with per-path ownership and permissions

description:
  - Creates multiple directories in a single task.
  - Absolute paths are created as-is; relative paths are created under C(base_path).
  - Per-path C(owner), C(group) and C(mode) override the global defaults.

options:
  base_path:
    description:
      - Base directory prepended to all relative paths.
    type: str
    default: "/"
  owner:
    description:
      - Default owner for all directories (can be overridden per path).
    type: str
  group:
    description:
      - Default group for all directories (can be overridden per path).
    type: str
  mode:
    description:
      - Default octal permission mode for all directories, e.g. C("0755").
    type: str
    default: "0755"
  paths:
    description:
      - List of directory specifications.
    type: list
    elements: dict
    required: true
    suboptions:
      path:
        description: Absolute or relative directory path.
        type: str
        required: true
      owner:
        description: Override owner for this directory.
        type: str
      group:
        description: Override group for this directory.
        type: str
      mode:
        description: Override octal permission mode for this directory.
        type: str
"""

EXAMPLES = r"""
- name: Create custom directory tree
  bodsch.core.directories:
    base_path: /srv/app
    owner: appuser
    group: appgroup
    mode: "0775"
    paths:
      - path: data/cache          # → /srv/app/data/cache  (global owner/group/mode)
        owner: cacheuser          # owner override
        mode: "0770"
      - path: /opt/shared         # → /opt/shared          (absolute, global defaults)
      - path: tmp                 # → /srv/app/tmp
        mode: "0700"
      - path: /var/log/myapp      # → /var/log/myapp
        owner: syslog
        group: adm
        mode: "0750"
"""

RETURN = r"""
directories:
  description: Status details for each processed path.
  returned: always
  type: list
  elements: dict
  contains:
    path:
      description: The resolved absolute path.
      type: str
    created:
      description: Whether the directory was created in this run.
      type: bool
    changed:
      description: Whether ownership or permissions were changed.
      type: bool
    owner:
      description: Applied owner name.
      type: str
    group:
      description: Applied group name.
      type: str
    mode:
      description: Applied octal mode string.
      type: str
"""


class Directories:
    """Manage idempotent batch creation of directories on the target host.

    This class encapsulates all filesystem logic for the ``bodsch.core.directories``
    Ansible module.  It is instantiated once per task invocation and processes
    every entry in the ``paths`` parameter sequentially.

    Per-path attributes (``owner``, ``group``, ``mode``) take precedence over
    the corresponding module-level defaults stored as instance attributes.

    Attributes:
        module (AnsibleModule): The active Ansible module instance used for
            parameter access, logging, and result reporting.
        base_path (str): Root directory prepended to all relative path entries.
        global_owner (Optional[str]): Default Unix user name applied to every
            directory unless overridden per path.
        global_group (Optional[str]): Default Unix group name applied to every
            directory unless overridden per path.
        global_mode (Optional[str]): Default octal permission string (e.g.
            ``"0755"``) applied to every directory unless overridden per path.
        paths (List[Dict[str, Any]]): Parsed list of path specification dicts
            as provided by the module's ``paths`` argument.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """Initialise the ``Directories`` handler from Ansible module parameters.

        Reads all relevant parameters from *module* and stores them as instance
        attributes so that the helper methods can access them without
        threading the module object through every call.

        Args:
            module (AnsibleModule): Active Ansible module instance.  Must have
                been created with an ``argument_spec`` that includes
                ``base_path``, ``owner``, ``group``, ``mode``, and ``paths``.
        """
        self.module = module
        # self.module.log("Directories::__init__()")

        self.base_path = self.module.params.get("base_path")
        self.global_owner = self.module.params.get("owner")
        self.global_group = self.module.params.get("group")
        self.global_mode = self.module.params.get("mode")
        self.paths = self.module.params.get("paths")

    def run(self) -> Dict[str, Any]:
        """Iterate over all path specifications and ensure each directory exists.

        For every entry in ``self.paths`` the method:

        1. Merges per-path attributes with the module-level defaults.
        2. Resolves the final absolute path via :meth:`_resolve_path`.
        3. Delegates filesystem work to :meth:`ensure_directory`.
        4. Aggregates individual results and derives the overall ``changed``
           flag.

        On any ``ValueError`` or ``OSError`` raised by :meth:`ensure_directory`
        the module fails immediately via ``AnsibleModule.fail_json``, reporting
        the offending path and all results collected so far.

        Returns:
            Dict[str, Any]: A dictionary suitable for passing directly to
            ``AnsibleModule.exit_json``.  Contains:

            - ``changed`` (bool): ``True`` if at least one directory was
              created or had its ownership/permissions updated.
            - ``directories`` (List[Dict]): One result dict per input path
              entry; see :meth:`ensure_directory` for the dict structure.
        """
        # self.module.log("Directories::run()")

        results: List[Dict[str, Any]] = []
        overall_changed = False

        for entry in self.paths:
            # Merge per-path values with global defaults
            effective_owner: Optional[str] = entry.get("owner") or self.global_owner
            effective_group: Optional[str] = entry.get("group") or self.global_group
            effective_mode: Optional[str] = entry.get("mode") or self.global_mode

            abs_path = self._resolve_path(
                base_path=self.base_path, path=entry.get("path")
            )

            try:
                result = self.ensure_directory(
                    abs_path=abs_path,
                    owner=effective_owner,
                    group=effective_group,
                    mode_str=effective_mode,
                    check_mode=self.module.check_mode,
                )
            except (ValueError, OSError) as exc:
                self.module.fail_json(
                    msg=str(exc),
                    path=abs_path,
                    results_so_far=results,
                )

            results.append(result)

            if result["changed"]:
                overall_changed = True

        return dict(
            changed=overall_changed,
            directories=results,
        )

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _parse_mode(self, mode_str: str) -> int:
        """Convert an octal mode string to its integer representation.

        Accepts both zero-padded (``"0775"``) and non-padded (``"775"``) forms.

        Args:
            mode_str (str): Octal permission string to convert.

        Returns:
            int: The integer value of the octal permission bits (e.g.
            ``0o775`` → ``509``).

        Raises:
            ValueError: If *mode_str* cannot be parsed as a base-8 integer.
                The original exception is chained for full traceback context.

        Examples:
            >>> self._parse_mode("0755")
            493
            >>> self._parse_mode("700")
            448
        """
        # self.module.log(f"Directories::_parse_mode(mode_str: {mode_str})")

        try:
            return int(mode_str, 8)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid mode '{mode_str}': {exc}") from exc

    def _resolve_path(self, base_path: str, path: str) -> str:
        """Resolve *path* to a normalised absolute filesystem path.

        The resolution strategy depends on whether *path* is absolute:

        - **Absolute path** (starts with ``/``): returned as-is after
          ``os.path.normpath`` normalisation (removes redundant separators and
          ``.`` / ``..`` components).
        - **Relative path**: joined with *base_path* and then normalised.

        Args:
            base_path (str): Root directory used as the prefix for relative
                paths.  Should be an absolute path itself.
            path (str): Path specification from the ``paths`` parameter entry.
                May be absolute or relative.

        Returns:
            str: Normalised absolute path string.

        Examples:
            >>> self._resolve_path("/srv/app", "data/cache")
            '/srv/app/data/cache'
            >>> self._resolve_path("/srv/app", "/opt/shared")
            '/opt/shared'
        """
        # self.module.log(f"Directories::_resolve_path(base_path: {base_path}, path: {path})")

        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(base_path, path))

    def _lookup_uid(self, owner: str) -> int:
        """Resolve a Unix user name to its numeric UID.

        Args:
            owner (str): Login name of the target user as it appears in
                ``/etc/passwd`` (or the configured NSS source).

        Returns:
            int: Numeric user identifier (UID) for *owner*.

        Raises:
            ValueError: If *owner* does not exist on the target system.
                Wraps the underlying ``KeyError`` from ``pwd.getpwnam`` with a
                human-readable message.
        """
        # self.module.log(f"Directories::_lookup_uid(owner: {owner})")

        try:
            return pwd.getpwnam(owner).pw_uid
        except KeyError:
            raise ValueError(f"User '{owner}' does not exist on target system")

    def _lookup_gid(self, group: str) -> int:
        """Resolve a Unix group name to its numeric GID.

        Args:
            group (str): Name of the target group as it appears in
                ``/etc/group`` (or the configured NSS source).

        Returns:
            int: Numeric group identifier (GID) for *group*.

        Raises:
            ValueError: If *group* does not exist on the target system.
                Wraps the underlying ``KeyError`` from ``grp.getgrnam`` with a
                human-readable message.
        """
        # self.module.log(f"Directories::_lookup_gid(group: {group})")

        try:
            return grp.getgrnam(group).gr_gid
        except KeyError:
            raise ValueError(f"Group '{group}' does not exist on target system")

    # ---------------------------------------------------------------------------
    # Core logic
    # ---------------------------------------------------------------------------

    def ensure_directory(
        self,
        abs_path: str,
        owner: Optional[str],
        group: Optional[str],
        mode_str: Optional[str],
        check_mode: bool,
    ) -> Dict[str, Any]:
        """Idempotently create *abs_path* and apply ownership and permissions.

        The method performs up to three distinct operations in sequence, each
        guarded by an idempotency check so that already-correct state is never
        touched unnecessarily:

        1. **Directory creation** – ``os.makedirs`` is called only when
           *abs_path* does not yet exist.  All intermediate directories are
           created as needed.  If the path exists but is not a directory an
           ``OSError`` is raised immediately.
        2. **Ownership adjustment** – ``os.chown`` is called only when the
           resolved UID or GID differs from the current ``st_uid`` / ``st_gid``
           values reported by ``os.stat``.  Passing ``-1`` for the UID or GID
           leaves the respective attribute unchanged (POSIX semantics).
        3. **Permission adjustment** – ``os.chmod`` is called only when the
           current permission bits (masked with ``stat.S_IMODE``) differ from
           the parsed *mode_str* value.

        In **check-mode** no writes are performed.  When the directory does not
        exist yet ``created`` is set to ``True`` to signal the expected change.
        For directories that already exist but whose ownership or permissions
        *might* need updating, ``attrs_changed`` is set conservatively to
        ``True`` (live stat data is not available after a simulated makedirs).

        Args:
            abs_path (str): Normalised absolute filesystem path to ensure.
                Must be the output of :meth:`_resolve_path`.
            owner (Optional[str]): Unix user name that should own the
                directory.  ``None`` means the owner is left unchanged.
            group (Optional[str]): Unix group name that should own the
                directory.  ``None`` means the group is left unchanged.
            mode_str (Optional[str]): Octal permission string (e.g.
                ``"0755"``).  ``None`` means permissions are left unchanged.
            check_mode (bool): When ``True`` the method simulates all
                operations without performing any actual filesystem writes.

        Returns:
            Dict[str, Any]: A result dictionary with the following keys:

            - ``path`` (str): The resolved absolute path.
            - ``created`` (bool): ``True`` if the directory was newly created.
            - ``changed`` (bool): ``True`` if the directory was created *or*
              ownership / permissions were modified.
            - ``owner`` (Optional[str]): The effective owner name that was
              applied (or would have been applied in check-mode).
            - ``group`` (Optional[str]): The effective group name that was
              applied (or would have been applied in check-mode).
            - ``mode`` (Optional[str]): The effective octal mode string that
              was applied (or would have been applied in check-mode).

        Raises:
            ValueError: If *mode_str* cannot be parsed (via :meth:`_parse_mode`)
                or if *owner* / *group* do not exist on the target system
                (via :meth:`_lookup_uid` / :meth:`_lookup_gid`).
            OSError: If *abs_path* exists but is not a directory, or if any
                low-level filesystem call (``makedirs``, ``chown``, ``chmod``)
                fails for a system-level reason (e.g. insufficient privileges).
        """
        # self.module.log(
        #     f"Directories::ensure_directory(abs_path: {abs_path}, owner: {owner}, group: {group}, "
        #     f"mode_str: {mode_str}, check_mode: {check_mode})"
        # )

        created = False
        attrs_changed = False

        mode_int = self._parse_mode(mode_str) if mode_str else None
        uid = self._lookup_uid(owner) if owner else None
        gid = self._lookup_gid(group) if group else None

        # ── 1. Create directory if missing ──────────────────────────────────────
        if not os.path.exists(abs_path):
            if not check_mode:
                os.makedirs(abs_path, mode=mode_int if mode_int is not None else 0o755)
            created = True

        elif not os.path.isdir(abs_path):
            raise OSError(f"Path exists but is not a directory: {abs_path}")

        # ── 2. Adjust ownership ──────────────────────────────────────────────────
        if not check_mode and os.path.exists(abs_path):
            current = os.stat(abs_path)

            want_uid = uid if uid is not None else -1
            want_gid = gid if gid is not None else -1

            needs_chown = (uid is not None and current.st_uid != uid) or (
                gid is not None and current.st_gid != gid
            )
            if needs_chown:
                os.chown(abs_path, want_uid, want_gid)
                attrs_changed = True

            # ── 3. Adjust permissions ────────────────────────────────────────────
            if mode_int is not None:
                current_mode = stat_module.S_IMODE(current.st_mode)
                if current_mode != mode_int:
                    os.chmod(abs_path, mode_int)
                    attrs_changed = True

        elif check_mode and (
            uid is not None or gid is not None or mode_int is not None
        ):
            # In check-mode live stat data is unavailable after a simulated
            # makedirs, so we conservatively assume attributes need updating
            # for directories that already exist.
            attrs_changed = not created

        return {
            "path": abs_path,
            "created": created,
            "changed": created or attrs_changed,
            "owner": owner,
            "group": group,
            "mode": mode_str,
        }


def main() -> None:
    """Module entry point: parse arguments, delegate to :class:`Directories`, exit.

    Defines the full Ansible ``argument_spec``, constructs the
    :class:`Directories` handler, invokes :meth:`Directories.run`, and
    forwards the result to ``AnsibleModule.exit_json``.

    The function never returns normally; control is transferred to Ansible
    via ``exit_json`` (success) or ``fail_json`` (error inside ``run``).
    """
    args = dict(
        base_path=dict(type="str", default="/"),
        owner=dict(type="str", default=None),
        group=dict(type="str", default=None),
        mode=dict(type="str", default="0755"),
        paths=dict(
            type="list",
            elements="dict",
            required=True,
            options=dict(
                path=dict(type="str", required=True),
                owner=dict(type="str", default=None),
                group=dict(type="str", default=None),
                mode=dict(type="str", default=None),
            ),
        ),
    )
    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    module_wrapper = Directories(module)
    result = module_wrapper.run()

    # module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
