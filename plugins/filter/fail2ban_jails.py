# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ansible.errors import AnsibleFilterError
from ansible.utils.display import Display

__metaclass__ = type

display = Display()

DOCUMENTATION = r"""
---
module: f2b_merge_jails
version_added: "1.0.0"
author:
  - "Bodo Schulz (@bodsch) <me+ansible@bodsch.me>"

short_description: Merge Fail2Ban jail definitions by name.
description:
  - Merge two lists of Fail2Ban jail definitions.
  - Entries are matched by their C(name) attribute.
  - If a jail exists in both input lists, the resulting jail is built by
    merging both dictionaries, with values from the second list taking
    precedence.
  - Jails that only exist in one list are preserved unchanged.
  - The final result is sorted by the C(name) field.

notes:
  - This file implements Ansible filter plugins.
  - The filters are exposed as C(f2b_merge_jails) and C(merge_jails).
  - The filter expects both inputs to be lists of dictionaries containing a
    C(name) key.

options: {}
"""

EXAMPLES = r"""
- name: Merge jail defaults with user-defined jail overrides
  ansible.builtin.set_fact:
    merged_jails: "{{ fail2ban_jail_defaults | f2b_merge_jails(fail2ban_jails) }}"

- name: Use the alias filter name
  ansible.builtin.set_fact:
    merged_jails: "{{ fail2ban_jail_defaults | merge_jails(fail2ban_jails) }}"

- name: Example input and merged output
  ansible.builtin.set_fact:
    fail2ban_jail_defaults:
      - name: sshd
        enabled: true
        port: ssh
        bantime: 600
      - name: nginx-http-auth
        enabled: false
    fail2ban_jails:
      - name: sshd
        bantime: 3600
      - name: dovecot
        enabled: true
    merged_jails: "{{ fail2ban_jail_defaults | f2b_merge_jails(fail2ban_jails) }}"
"""

RETURN = r"""
_value:
  description:
    - Sorted list of merged jail definitions.
    - Each item is a dictionary representing one Fail2Ban jail.
    - Matching entries are merged by C(name), and values from the second input
      list override values from the first input list.
  type: list
  elements: dict
  returned: always
  sample:
    - name: dovecot
      enabled: true
    - name: nginx-http-auth
      enabled: false
    - name: sshd
      enabled: true
      port: ssh
      bantime: 3600
"""


class FilterModule(object):
    """
    Ansible filter plugin for merging Fail2Ban jail definitions.

    The plugin exposes two filter names that both delegate to the same merge
    implementation:
    C(f2b_merge_jails) and C(merge_jails).
    """

    def filters(self) -> Dict[str, Any]:
        """
        Return the filter mapping exposed to Ansible.

        Returns:
            dict: Mapping of filter names to callables.
        """
        return {
            "f2b_merge_jails": self.merge_jails,
            "merge_jails": self.merge_jails,
        }

    def __merge_two_dicts(
        self,
        x: Mapping[str, Any],
        y: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge two dictionaries without mutating the inputs.

        Values from the second mapping override values from the first mapping.

        Args:
            x: Base dictionary.
            y: Override dictionary.

        Returns:
            dict: New merged dictionary.
        """
        result = deepcopy(dict(x))
        result.update(deepcopy(dict(y)))
        return result

    def __search(
        self,
        data: Sequence[Mapping[str, Any]],
        name: str,
    ) -> Optional[Mapping[str, Any]]:
        """
        Search a list of jail definitions for a given jail name.

        Args:
            data: Sequence of jail dictionaries.
            name: Jail name to search for.

        Returns:
            Optional[Mapping[str, Any]]: Matching jail dictionary or C(None).
        """
        for item in data:
            if item.get("name") == name:
                return item

        return None

    def __sort_list(
        self,
        items: Sequence[Mapping[str, Any]],
        sort_key: str,
    ) -> List[Dict[str, Any]]:
        """
        Return a new list sorted by the given dictionary key.

        Args:
            items: Sequence of dictionaries to sort.
            sort_key: Dictionary key used for sorting.

        Returns:
            list: Sorted list of copied dictionaries.
        """
        return sorted(
            (deepcopy(dict(item)) for item in items),
            key=lambda item: item.get(sort_key, ""),
        )

    def __validate_entries(
        self,
        value: Sequence[Mapping[str, Any]],
        variable_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Validate and normalize the input jail list.

        Args:
            value: Input sequence expected to contain dictionaries with a
                C(name) key.
            variable_name: Human-readable variable name used in error messages.

        Returns:
            list: Normalized list of copied dictionaries.

        Raises:
            AnsibleFilterError: If the input is not a sequence of dictionaries
                containing a C(name) key.
        """
        if value is None:
            return []

        if not isinstance(value, (list, tuple)):
            raise AnsibleFilterError(
                f"{variable_name} must be a list of dictionaries, got {type(value).__name__}."
            )

        result: List[Dict[str, Any]] = []

        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise AnsibleFilterError(
                    f"{variable_name}[{index}] must be a dictionary, got {type(item).__name__}."
                )

            if "name" not in item:
                raise AnsibleFilterError(
                    f"{variable_name}[{index}] is missing the required 'name' key."
                )

            result.append(deepcopy(dict(item)))

        return result

    def merge_jails(
        self,
        defaults: Sequence[Mapping[str, Any]],
        data: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge two lists of Fail2Ban jail definitions by jail name.

        The function matches entries by their C(name) key. If a jail exists in
        both lists, the result is a dictionary merge where values from C(data)
        override values from C(defaults). Jails present in only one list are
        preserved unchanged. The final result is sorted by C(name).

        Args:
            defaults: Base jail definitions.
            data: Override jail definitions.

        Returns:
            list: Sorted list of merged jail dictionaries.
        """
        display.vv(
            f"bodsch.core.f2b_merge_jails(defaults={defaults}, data={data})"
        )

        normalized_defaults = self.__validate_entries(defaults, "defaults")
        normalized_data = self.__validate_entries(data, "data")

        if len(normalized_defaults) == 0:
            return self.__sort_list(normalized_data, "name")

        if len(normalized_data) == 0:
            return self.__sort_list(normalized_defaults, "name")

        result: List[Dict[str, Any]] = []
        consumed_default_names = set()

        for item in normalized_data:
            jail_name = item["name"]
            default_item = self.__search(normalized_defaults, jail_name)

            if default_item is None:
                result.append(deepcopy(item))
            else:
                result.append(self.__merge_two_dicts(default_item, item))
                consumed_default_names.add(jail_name)

        remaining_defaults = [
            item
            for item in normalized_defaults
            if item["name"] not in consumed_default_names
        ]

        return self.__sort_list(result + remaining_defaults, "name")
