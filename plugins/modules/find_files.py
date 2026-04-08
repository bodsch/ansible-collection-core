# Copyright: (c) 2017, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module to collect stat information for multiple paths."""

from __future__ import annotations

import hashlib
import os
import stat
from typing import Any, Dict, List, Optional, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_bytes

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: find_files
version_added: "2.12.0"
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Collect file status information for multiple paths
description:
  - Collects file status information for multiple paths in a single module call.
  - Supports symbolic link handling via C(follow).
  - Optionally calculates a checksum for regular files.


options:
  file_list:
    description:
      - List of file system paths to inspect.
    type: list
    elements: str
    required: true
    aliases:
      - names
  follow:
    description:
      - Follow symbolic links instead of returning information about the link itself.
    type: bool
    default: false
  get_checksum:
    description:
      - Calculate a checksum for regular files.
      - Checksums are only returned for existing regular files.
    type: bool
    default: true
  checksum_algorithm:
    description:
      - Hash algorithm used when C(get_checksum=true).
    type: str
    default: sha256
    choices:
      - sha1
      - sha224
      - sha256
      - sha384
      - sha512
    aliases:
      - checksum
      - checksum_algo
notes:
  - The module never changes remote state.
  - Missing files are reported with C(exists=false).
"""

EXAMPLES = r"""
- name: Collect file information for multiple paths
  bodsch.core.find_files:
    file_list:
      - /etc/passwd
      - /etc/shadow
      - /does/not/exist

- name: Follow symbolic links
  bodsch.core.find_files:
    file_list:
      - /usr/bin/python3
      - /bin/sh
    follow: true

- name: Disable checksum calculation
  bodsch.core.find_files:
    file_list:
      - /var/log/syslog
      - /var/log/auth.log
    get_checksum: false

- name: Use SHA-512 for checksums
  bodsch.core.find_files:
    names:
      - /etc/hosts
      - /etc/resolv.conf
    get_checksum: true
    checksum_algorithm: sha512
"""

RETURN = r"""
stat:
  description:
    - List of file status results, one entry per requested path.
  returned: always
  type: list
  elements: dict
  sample:
    - path: /etc/passwd
      exists: true
      mode: "0644"
      uid: 0
      gid: 0
      size: 2480
      checksum: "3b5d5c3712955042212316173ccf37be"
      checksum_algorithm: sha256
    - path: /does/not/exist
      exists: false
changed:
  description:
    - Always C(false), because this module only reads file metadata.
  returned: always
  type: bool
  sample: false
"""

# ---------------------------------------------------------------------------------------


class StatEntry(TypedDict, total=False):
    """Typed result structure for a single path."""

    exists: bool
    path: str
    mode: str
    uid: int
    gid: int
    size: int
    checksum: str
    checksum_algorithm: str


class ModuleResult(TypedDict):
    """Typed module return structure."""

    changed: bool
    stat: List[StatEntry]


def format_output(path: str, exists: bool, st: Optional[os.stat_result]) -> StatEntry:
    """Build the public result dictionary for a single path.

    Args:
        path: Original input path.
        exists: Whether the path could be stat'ed successfully.
        st: Stat result object for the path, or None.

    Returns:
        A result dictionary compatible with the module output format.
    """
    output: StatEntry = {
        "exists": bool(exists),
        "path": path,
    }

    if not exists or st is None:
        return output

    output["mode"] = f"{stat.S_IMODE(st.st_mode):04o}"
    output["uid"] = st.st_uid
    output["gid"] = st.st_gid
    output["size"] = st.st_size

    return output


class FindFiles:
    """Collect stat information for multiple file system paths."""

    def __init__(self, module: AnsibleModule) -> None:
        """Initialize the collector from module parameters.

        Args:
            module: Active Ansible module instance.
        """
        self.module = module
        self.module.log("FindFiles::__init__()")

        self.file_list: List[str] = self._normalize_file_list(module.params.get("file_list"))
        self.follow: bool = bool(module.params.get("follow"))
        self.get_checksum: bool = bool(module.params.get("get_checksum"))
        self.checksum_algorithm: str = cast(str, module.params.get("checksum_algorithm"))

    def run(self) -> ModuleResult:
        """Collect stat information for all requested paths.

        Returns:
            Module result dictionary with unchanged state and stat entries.
        """
        self.module.log("FindFiles::run()")

        result: List[StatEntry] = []

        for file_path in self.file_list:
            self.module.log(f" - file: {file_path}")
            result.append(self._collect_file_data(file_path))

        return {
            "changed": False,
            "stat": result,
        }

    def _normalize_file_list(self, value: Any) -> List[str]:
        """Validate and normalize the file list parameter.

        Args:
            value: Raw module parameter value.

        Returns:
            A normalized list of file paths.

        Raises:
            AnsibleModule.fail_json: If the input value is invalid.
        """
        if not isinstance(value, list):
            self.module.fail_json(msg="'file_list' must be a list of path strings.")

        invalid_entries = [entry for entry in value if not isinstance(entry, str)]
        if invalid_entries:
            self.module.fail_json(
                msg="'file_list' must contain only strings.",
                invalid_entries=invalid_entries,
            )

        return value

    def _collect_file_data(self, path: str) -> StatEntry:
        """Collect result data for a single path.

        Args:
            path: File system path to inspect.

        Returns:
            Result dictionary for the given path.
        """
        st = self._stat_path(path)
        exists = st is not None
        output = format_output(path=path, exists=exists, st=st)

        if exists and st is not None and self.get_checksum and stat.S_ISREG(st.st_mode):
            checksum = self._calculate_checksum(path)
            if checksum is not None:
                output["checksum"] = checksum
                output["checksum_algorithm"] = self.checksum_algorithm

        return output

    def _stat_path(self, path: str) -> Optional[os.stat_result]:
        """Read stat information for a path.

        Args:
            path: File system path to inspect.

        Returns:
            The stat result on success, otherwise C(None).
        """
        b_path = to_bytes(path, errors="surrogate_or_strict")

        try:
            if self.follow:
                return os.stat(b_path)
            return os.lstat(b_path)
        except FileNotFoundError:
            self.module.log(f"   missing: {path}")
            return None
        except OSError as exc:
            self.module.log(
                f"   stat failed for '{path}': {exc.__class__.__name__}: {exc}"
            )
            return None

    def _calculate_checksum(self, path: str) -> Optional[str]:
        """Calculate the checksum of a regular file.

        Args:
            path: Path to the file.

        Returns:
            Hex digest string on success, otherwise C(None).
        """
        b_path = to_bytes(path, errors="surrogate_or_strict")

        try:
            digest = hashlib.new(self.checksum_algorithm)
        except ValueError as exc:
            self.module.log(
                f"   invalid checksum algorithm '{self.checksum_algorithm}': {exc}"
            )
            return None

        try:
            with open(b_path, "rb") as file_handle:
                for chunk in iter(lambda: file_handle.read(65536), b""):
                    digest.update(chunk)
        except OSError as exc:
            self.module.log(
                f"   checksum failed for '{path}': {exc.__class__.__name__}: {exc}"
            )
            return None

        return digest.hexdigest()


def main() -> None:
    """Entrypoint for the Ansible module."""
    argument_spec: Dict[str, Any] = {
        "file_list": dict(type="list", elements="str", required=True, aliases=["names"]),
        "follow": dict(type="bool", default=False),
        "get_checksum": dict(type="bool", default=False),
        "checksum_algorithm": dict(
            type="str",
            default="sha256",
            choices=["sha1", "sha224", "sha256", "sha384", "sha512"],
            aliases=["checksum", "checksum_algo"],
        ),
    }

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    finder = FindFiles(module)
    result = finder.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
