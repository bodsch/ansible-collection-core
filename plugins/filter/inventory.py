# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Dict, Iterable, Optional, Tuple

from ansible.errors import AnsibleFilterError
from ansible.utils.display import Display

display = Display()

"""
Ansible filter plugin: host_id

Resolves a stable host identifier across Ansible versions and fact-injection styles.

Resolution order:
1) ansible_facts['host']     (if present)
2) ansible_facts['hostname'] (standard setup fact)
3) inventory_hostname        (always available as magic var)

Usage:
  {{ (ansible_facts | default({})) | host_id(inventory_hostname) }}
"""


class FilterModule:
    """ """

    def filters(self):
        return {
            "hostname": self.hostname,
        }

    def hostname(
        self,
        facts: Optional[Dict[str, Any]] = None,
        inventory_hostname: Optional[str] = None,
        prefer: Optional[Iterable[str]] = None,
        default: str = "",
    ) -> str:
        """
        Return a host identifier string using a preference list over facts.

        Args:
            facts: Typically 'ansible_facts' (may be undefined/None).
            inventory_hostname: Magic var 'inventory_hostname' as last-resort fallback.
            prefer: Iterable of fact keys to try in order (default: ('host', 'hostname')).
            default: Returned if nothing else is available.

        Returns:
            Resolved host identifier as string.
        """
        display.vv(
            f"bodsch.core.hostname(self, facts, inventory_hostname: '{inventory_hostname}', prefer: '{prefer}', default: '{default}')"
        )

        facts_dict = self._as_dict(facts)
        keys: Tuple[str, ...] = (
            tuple(prefer) if prefer is not None else ("host", "hostname")
        )

        for key in keys:
            val = facts_dict.get(key)
            if val not in (None, ""):
                display.vv(f"= result: {str(val)}")
                return str(val)

        if inventory_hostname not in (None, ""):
            display.vv(f"= result: {str(inventory_hostname)}")
            return str(inventory_hostname)

        display.vv(f"= result: {str(default)}")

        return str(default)

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        """ """
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        raise AnsibleFilterError(
            f"hostname expects a dict-like ansible_facts, got: {type(value)!r}"
        )
