#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import dns.exception
from dns.resolver import Resolver

__metaclass__ = type


def dns_lookup(dns_name, timeout=3, dns_resolvers=[]):
    """
    Perform a simple DNS lookup, return results in a dictionary
    """
    resolver = Resolver()
    resolver.timeout = float(timeout)
    resolver.lifetime = float(timeout)

    result = {}

    if not dns_name:
        return {
            "addrs": [],
            "error": True,
            "error_msg": "No DNS Name for resolving given",
            "name": dns_name,
        }

    if dns_resolvers:
        resolver.nameservers = dns_resolvers
    try:
        records = resolver.resolve(dns_name)
        result = {
            "addrs": [ii.address for ii in records],
            "error": False,
            "error_msg": "",
            "name": dns_name,
        }
    except dns.resolver.NXDOMAIN:
        result = {
            "addrs": [],
            "error": True,
            "error_msg": "No such domain",
            "name": dns_name,
        }
    except dns.resolver.NoNameservers as e:
        result = {
            "addrs": [],
            "error": True,
            "error_msg": repr(e),
            "name": dns_name,
        }
    except dns.resolver.Timeout:
        result = {
            "addrs": [],
            "error": True,
            "error_msg": "Timed out while resolving",
            "name": dns_name,
        }
    except dns.resolver.NameError as e:
        result = {
            "addrs": [],
            "error": True,
            "error_msg": repr(e),
            "name": dns_name,
        }
    except dns.exception.DNSException as e:
        result = {
            "addrs": [],
            "error": True,
            "error_msg": f"Unhandled exception ({repr(e)})",
            "name": dns_name,
        }

    return result
