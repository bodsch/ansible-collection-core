#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to manage custom local Ansible facts.

The module writes executable ``.fact`` files below ``/etc/ansible/facts.d`` and
stores a cached JSON representation together with a checksum file below
``/var/cache/ansible/<name>``. The cache is used to detect content changes
efficiently and to keep the generated fact file idempotent.
"""

from __future__ import absolute_import, division, print_function

import json
import os
from typing import Any, Dict, Final, List

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum
from ansible_collections.bodsch.core.plugins.module_utils.directory import (
    create_directory,
)
from ansible_collections.bodsch.core.plugins.module_utils.file import chmod, remove_file

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: facts
version_added: "1.0.10"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Manage custom local Ansible facts.

description:
  - Create or remove custom local Ansible facts.
  - Facts are written as executable C(.fact) files below
    C(/etc/ansible/facts.d).
  - The module also maintains a cached JSON copy and checksum file below
    C(/var/cache/ansible/<name>) to detect changes efficiently.
  - The resulting fact file prints JSON and can be consumed by Ansible as a
    standard local fact source.

attributes:
  check_mode:
    support: full

notes:
  - The module supports check mode.
  - The option O(facts) remains required to preserve the current module
    interface, even when O(state=absent).

options:
  state:
    description:
      - Desired state of the named local fact.
      - Use C(present) to create or update the fact.
      - Use C(absent) to remove the fact and its cache files.
    type: str
    choices:
      - present
      - absent
    default: present

  name:
    description:
      - Name of the fact file without the C(.fact) suffix.
    type: str
    required: true

  facts:
    description:
      - Dictionary containing the fact payload.
      - This value is written to the generated local fact file when
        O(state=present).
    type: dict
    required: true

  append:
    description:
      - Merge the provided facts into the existing cached facts.
      - If set to C(false), the provided facts replace the existing facts.
    type: bool
    default: true
"""

EXAMPLES = r"""
- name: Create custom facts
  bodsch.core.facts:
    state: present
    name: icinga2
    facts:
      version: "2.10"
      salt: "fgmklsdfnjyxnvjksdfbkuser"
      user: "icinga2"

- name: Replace an existing fact payload completely
  bodsch.core.facts:
    state: present
    name: application
    append: false
    facts:
      version: "1.4.2"
      environment: "production"

- name: Remove a local fact
  bodsch.core.facts:
    state: absent
    name: icinga2
    facts: {}
"""

RETURN = r"""
changed:
  description:
    - Indicates whether the module changed the managed host.
  returned: always
  type: bool
  sample: true

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
  sample: "The facts have been successfully written."
"""

# ---------------------------------------------------------------------------------------


class AnsibleFacts:
    """
    Manage custom local Ansible facts and their associated cache files.

    The public API of the class is intentionally small. The C(run()) method
    evaluates the requested state and delegates the implementation details to
    internal helper methods.
    """

    CACHE_ROOT: Final[str] = "/var/cache/ansible"
    FACTS_DIRECTORY: Final[str] = "/etc/ansible/facts.d"

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the module wrapper and resolve all configured paths.

        Args:
            module: Active Ansible module instance.
        """
        self.module = module

        self.state: str = module.params.get("state")
        self.name: str = module.params.get("name")
        self.facts: Dict[str, Any] = dict(module.params.get("facts") or {})
        self.append: bool = bool(module.params.get("append", True))

        self.cache_directory: str = os.path.join(self.CACHE_ROOT, self.name)
        self.checksum_file: str = os.path.join(self.cache_directory, "facts.checksum")
        self.json_file: str = os.path.join(self.cache_directory, "facts.json")
        self.facts_file: str = os.path.join(self.FACTS_DIRECTORY, f"{self.name}.fact")

        self.checksum = Checksum(module)

    def run(self) -> Dict[str, Any]:
        """
        Execute the requested fact management workflow.

        Returns:
            A stable Ansible result dictionary containing at least C(changed),
            C(failed), and C(msg).
        """
        if self.state == "absent":
            return self._remove_fact_files()

        current_facts = self._load_existing_facts()
        target_facts = self._build_target_facts(current_facts)

        if not self._has_changed(current_facts, target_facts):
            return self._build_result(
                changed=False,
                failed=False,
                msg="There are no changes.",
            )

        if self.module.check_mode:
            return self._build_result(
                changed=True,
                failed=False,
                msg="The facts would be successfully written.",
            )

        self._ensure_directories()
        self._write_facts(target_facts)

        return self._build_result(
            changed=True,
            failed=False,
            msg="The facts have been successfully written.",
        )

    def list_files(self, startpath: str) -> None:
        """
        Log a recursive directory tree for debugging purposes.

        Args:
            startpath: Directory path to traverse recursively.
        """
        for root, _dirs, files in os.walk(startpath):
            level = root.replace(startpath, "").count(os.sep)
            indent = " " * 4 * level
            self.module.log(msg=f"{indent}{os.path.basename(root)}/")

            subindent = " " * 4 * (level + 1)
            for file_name in files:
                self.module.log(msg=f"{subindent}{file_name}")

    def _build_result(self, changed: bool, failed: bool, msg: str) -> Dict[str, Any]:
        """
        Create a normalized Ansible result payload.

        Args:
            changed: Whether the module changed the managed host.
            failed: Whether the module execution failed.
            msg: Human-readable result message.

        Returns:
            Normalized result dictionary.
        """
        return {
            "changed": changed,
            "failed": failed,
            "msg": msg,
        }

    def _managed_files(self) -> List[str]:
        """
        Return all files managed by this module instance.

        Returns:
            List of managed file paths.
        """
        return [self.checksum_file, self.json_file, self.facts_file]

    def _ensure_directories(self) -> None:
        """
        Ensure that all required directories exist.
        """
        create_directory(self.cache_directory)
        create_directory(self.FACTS_DIRECTORY, mode="0775")

    def _remove_fact_files(self) -> Dict[str, Any]:
        """
        Remove the fact file and all related cache files.

        Returns:
            Normalized result dictionary.
        """
        existing_files = [
            path for path in self._managed_files() if os.path.exists(path)
        ]

        if not existing_files:
            return self._build_result(
                changed=False,
                failed=False,
                msg="There are no changes.",
            )

        if self.module.check_mode:
            return self._build_result(
                changed=True,
                failed=False,
                msg="The facts would be successfully removed.",
            )

        for path in existing_files:
            remove_file(path)

        return self._build_result(
            changed=True,
            failed=False,
            msg="The facts have been successfully removed.",
        )

    def _load_existing_facts(self) -> Dict[str, Any]:
        """
        Load the cached JSON representation of the current facts.

        The cache is only trusted when the generated fact file exists as well.
        If the fact file is missing, the current state is treated as empty to
        force a clean recreation.

        Returns:
            Dictionary containing the currently cached facts.
        """
        if not os.path.exists(self.facts_file):
            return {}

        if not os.path.exists(self.json_file):
            return {}

        with open(self.json_file, "r", encoding="utf-8") as file_handle:
            return dict(json.load(file_handle) or {})

    def _build_target_facts(self, current_facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the target fact payload that should be written.

        Args:
            current_facts: Currently cached fact payload.

        Returns:
            Final fact dictionary to persist.
        """
        if not self.append:
            return dict(self.facts)

        merged_facts = dict(current_facts)
        merged_facts.update(self.facts)
        return merged_facts

    def _has_changed(
        self,
        current_facts: Dict[str, Any],
        target_facts: Dict[str, Any],
    ) -> bool:
        """
        Compare the current facts with the target facts.

        Args:
            current_facts: Currently cached fact payload.
            target_facts: Desired fact payload.

        Returns:
            C(True) if the fact content has changed, otherwise C(False).
        """
        old_checksum = self.checksum.checksum(current_facts)
        new_checksum = self.checksum.checksum(target_facts)
        return old_checksum != new_checksum

    def _write_facts(self, facts_data: Dict[str, Any]) -> None:
        """
        Persist the fact payload, cache file, and checksum.

        Args:
            facts_data: Final fact payload to write.
        """
        fact_payload = json.dumps(facts_data, indent=2, sort_keys=True)
        fact_script = (
            "#!/usr/bin/env bash\n"
            "# generated by ansible\n"
            "cat <<EOF\n"
            f"{fact_payload}\n"
            "EOF\n"
        )

        with open(self.facts_file, "w", encoding="utf-8") as file_handle:
            file_handle.write(fact_script)

        with open(self.json_file, "w", encoding="utf-8") as file_handle:
            json.dump(facts_data, file_handle, indent=2, sort_keys=True)

        chmod(self.facts_file, "0775")
        self.checksum.write_checksum(
            self.checksum_file,
            self.checksum.checksum(facts_data),
        )


def main() -> None:
    """
    Create the Ansible module instance, execute the workflow, and return the
    result payload.
    """
    args = dict(
        state=dict(
            type="str",
            choices=[
                "present",
                "absent",
            ],
            default="present",
        ),
        name=dict(
            type="str",
            required=True,
        ),
        facts=dict(
            type="dict",
            required=True,
        ),
        append=dict(
            type="bool",
            required=False,
            default=True,
        ),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    obj = AnsibleFacts(module)
    result = obj.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
