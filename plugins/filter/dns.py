# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, print_function)

from dns.resolver import Resolver
import dns.exception

__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
    """
    def filters(self):
        return {
            'dns_lookup': self.dns_lookup
        }

    def dns_lookup(dns_name, timeout=3, extern_resolver=[]):
        """
          Perform a simple DNS lookup, return results in a dictionary
        """
        resolver = Resolver()
        resolver.timeout = float(timeout)
        resolver.lifetime = float(timeout)

        result = {}

        if extern_resolver:
            resolver.nameservers = extern_resolver
        try:
            records = resolver.resolve(dns_name)
            result = {
                "addrs": [ii.address for ii in records],
                "error": "",
                "name": dns_name,
            }

        except dns.resolver.NXDOMAIN:
            result = {
                "addrs": [],
                "error": f"No such domain {dns_name}",
                "name": dns_name,
            }

        except dns.resolver.NoNameservers as e:
            result = {
                "addrs": [],
                "error": repr(e),
                "name": dns_name,
            }

        except dns.resolver.Timeout:
            result = {
                "addrs": [],
                "error": f"Timed out while resolving {dns_name}",
                "name": dns_name,
            }
        except dns.resolver.NameError as e:
            result = {
                "addrs": [],
                "error": repr(e),
                "name": dns_name,
            }
        # print(f"Timed out while resolving {dns_name}")
        except dns.exception.DNSException as e:
            result = {
                "addrs": [],
                "error": f"Unhandled exception ({repr(e)})",
                "name": dns_name,
            }

        return result
