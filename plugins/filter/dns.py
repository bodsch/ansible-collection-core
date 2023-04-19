# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, print_function)
from ansible.utils.display import Display
from ansible_collections.bodsch.core.plugins.module_utils.dns_lookup import dns_lookup

__metaclass__ = type
display = Display()


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'dns_lookup': self.lookup
        }

    def lookup(self, dns_name, timeout=3, dns_resolvers=[]):
        """
          use a simple DNS lookup, return results in a dictionary

          similar to
          {'addrs': [], 'error': True, 'error_msg': 'No such domain instance', 'name': 'instance'}
        """
        display.v(f"lookup({dns_name}, {timeout}, {dns_resolvers})")

        result = dns_lookup(dns_name, timeout, dns_resolvers)

        display.v(f"= return : {result}")

        return result
