#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to normalize account defaults and resolve a user's primary group.
"""

from __future__ import absolute_import, division, print_function

import grp
import pwd
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: account_defaults
version_added: "2.11.0"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Resolve account defaults and primary group information

description:
  - Normalizes a user account value from an explicit user or a fallback default user.
  - Optionally resolves the user's primary group from the local system account database.
  - This module does not modify system state and always returns C(changed=false).

options:
  user:
    description:
      - Explicit account name to use.
      - If omitted or empty, O(default_user) is used.
    required: false
    type: str
  default_user:
    description:
      - Fallback account name used when O(user) is omitted or empty.
    required: false
    type: str
  group:
    description:
      - Explicit group name to use.
      - If omitted or empty, the primary group of the resolved user is detected.
    required: false
    type: str
  fail_on_missing_user:
    description:
      - Fail when the resolved user does not exist in the local account database.
      - If set to C(false), missing user information is returned without failing.
    required: false
    type: bool
    default: true

notes:
  - The module uses Python's C(pwd) and C(grp) standard library modules.
  - The module is intended for Unix-like targets.
"""

EXAMPLES = r"""
- name: Resolve account data from explicit user
  account_defaults:
    user: "www-data"

- name: Resolve account data from fallback user
  account_defaults:
    default_user: "nginx"

- name: Use explicit group and skip primary group detection
  account_defaults:
    user: "php-fpm"
    group: "web"

- name: Do not fail on missing user
  account_defaults:
    user: "unknown-user"
    fail_on_missing_user: false
  register: account_result

- name: Apply resolved values
  ansible.builtin.set_fact:
    php_fpm_pool_user: "{{ account_result.user }}"
    php_fpm_pool_group: "{{ account_result.group }}"
"""

RETURN = r"""
user:
  description: Final resolved user name.
  returned: always
  type: str
  sample: "www-data"

group:
  description: Final resolved group name.
  returned: always
  type: str
  sample: "www-data"

uid:
  description: Numeric user ID of the resolved user.
  returned: when user exists
  type: int
  sample: 33

gid:
  description: Numeric primary group ID of the resolved user.
  returned: when user exists
  type: int
  sample: 33

source_user:
  description: Source used to determine the final user value.
  returned: always
  type: str
  sample: "default"

source_group:
  description: Source used to determine the final group value.
  returned: always
  type: str
  sample: "primary"

user_exists:
  description: Indicates whether the resolved user exists in the local account database.
  returned: always
  type: bool
  sample: true

changed:
  description: This module never changes system state.
  returned: always
  type: bool
  sample: false
"""

# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AccountResolution:
    """Structured result for resolved account data."""

    user: str
    group: str
    uid: Optional[int]
    gid: Optional[int]
    source_user: str
    source_group: str
    user_exists: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result object into an Ansible-compatible dictionary."""
        return {
            "user": self.user,
            "group": self.group,
            "uid": self.uid,
            "gid": self.gid,
            "source_user": self.source_user,
            "source_group": self.source_group,
            "user_exists": self.user_exists,
        }


class AccountDefaults(object):
    """
    Resolve normalized account values for user and group.

    The module accepts an explicit user/group combination or derives missing
    values from a default user and the user's primary group.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """Store the Ansible module instance."""
        self.module = module
        self.module.log("AccountDefaults::__init__()")

    def run(self) -> Dict[str, Any]:
        """
        Execute the module logic.

        Returns:
            A result dictionary for Ansible.
        """
        self.module.log("AccountDefaults::run()")

        result: Dict[str, Any] = {
            "changed": False,
            "failed": False,
            "check_mode": bool(self.module.check_mode),
        }

        resolution = self.resolve_account()
        result.update(resolution.to_dict())

        return result

    def resolve_account(self) -> AccountResolution:
        """
        Resolve the final user and group values.

        Returns:
            A structured account resolution result.

        Raises:
            AnsibleModule.fail_json: If no usable user value is available or
                if user resolution fails and fail_on_missing_user is enabled.
        """
        self.module.log("AccountDefaults::resolve_account()")

        explicit_user = self._normalized_str(self.module.params.get("user"))
        default_user = self._normalized_str(self.module.params.get("default_user"))
        explicit_group = self._normalized_str(self.module.params.get("group"))
        fail_on_missing_user = bool(self.module.params.get("fail_on_missing_user"))

        resolved_user, source_user = self._resolve_user(
            explicit_user=explicit_user,
            default_user=default_user,
        )

        user_entry = self.user_data(resolved_user)

        if user_entry is None:
            if fail_on_missing_user:
                self.module.fail_json(
                    msg=f"Unable to resolve local account data for user '{resolved_user}'.",
                    changed=False,
                    failed=True,
                    user=resolved_user,
                    group=explicit_group or "",
                    uid=None,
                    gid=None,
                    source_user=source_user,
                    source_group="explicit" if explicit_group else "unresolved",
                    user_exists=False,
                )

            return AccountResolution(
                user=resolved_user,
                group=explicit_group or "",
                uid=None,
                gid=None,
                source_user=source_user,
                source_group="explicit" if explicit_group else "unresolved",
                user_exists=False,
            )

        if explicit_group:
            resolved_group = explicit_group
            source_group = "explicit"
        else:
            resolved_group = self.group_data(user_entry.pw_gid)
            source_group = "primary"

        return AccountResolution(
            user=resolved_user,
            group=resolved_group,
            uid=user_entry.pw_uid,
            gid=user_entry.pw_gid,
            source_user=source_user,
            source_group=source_group,
            user_exists=True,
        )

    def user_data(self, username: str) -> Optional[pwd.struct_passwd]:
        """
        Read local passwd data for a given user.

        Args:
            username: User name to resolve.

        Returns:
            The passwd entry if the user exists, otherwise C(None).
        """
        self.module.log(f"AccountDefaults::user_data(username: {username})")

        try:
            return pwd.getpwnam(username)
        except KeyError:
            return None

    def group_data(self, gid: int) -> str:
        """
        Resolve the local group name for a numeric group ID.

        Args:
            gid: Primary group ID.

        Returns:
            The group name for the given GID.

        Raises:
            AnsibleModule.fail_json: If the group cannot be resolved.
        """
        self.module.log(f"AccountDefaults::group_data(gid: {gid})")

        try:
            return grp.getgrgid(gid).gr_name
        except KeyError:
            self.module.fail_json(
                msg=f"Unable to resolve local group name for gid '{gid}'.",
                changed=False,
                failed=True,
                gid=gid,
            )
            raise AssertionError("unreachable")

    def _resolve_user(
        self,
        explicit_user: Optional[str],
        default_user: Optional[str],
    ) -> tuple[str, str]:
        """
        Resolve the effective user from explicit and fallback values.

        Args:
            explicit_user: Explicitly provided user value.
            default_user: Fallback user value.

        Returns:
            A tuple of resolved user name and source identifier.

        Raises:
            AnsibleModule.fail_json: If neither explicit nor default user is available.
        """
        if explicit_user:
            return explicit_user, "explicit"

        if default_user:
            return default_user, "default"

        self.module.fail_json(
            msg="Either 'user' or 'default_user' must be provided.",
            changed=False,
            failed=True,
        )
        raise AssertionError("unreachable")

    @staticmethod
    def _normalized_str(value: Any) -> Optional[str]:
        """
        Normalize a potential string input.

        Args:
            value: Input value to normalize.

        Returns:
            A stripped string or C(None) if the value is empty or missing.
        """
        if value is None:
            return None

        if not isinstance(value, str):
            value = str(value)

        normalized = value.strip()
        return normalized or None


def main() -> None:
    """Initialize the module and execute the resolver."""
    argument_spec = dict(
        user=dict(type="str", required=False),
        default_user=dict(type="str", required=False),
        group=dict(type="str", required=False),
        fail_on_missing_user=dict(type="bool", default=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    resolver = AccountDefaults(module)
    result = resolver.run()

    module.log(msg=f"= result: {result}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
