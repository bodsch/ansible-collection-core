#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Utility helpers for DNS lookups used by Ansible collection code.

This file currently exposes a single public function, ``dns_lookup()``, which
performs a DNS lookup by using dnspython and returns a normalized dictionary
result that can be consumed by higher-level modules or plugins.
"""

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, Optional, Sequence, Union

import dns.exception
import dns.resolver
from dns.resolver import Resolver

__metaclass__ = type

DnsLookupResult = Dict[str, Any]


def _error_result(name: Optional[str], message: str) -> DnsLookupResult:
    """
    Build a normalized error result dictionary.

    Args:
        name: DNS name that was requested.
        message: Human-readable error message.

    Returns:
        dict: Result payload with a stable schema.
    """
    return {
        "addrs": [],
        "error": True,
        "error_msg": message,
        "name": name,
    }


def _success_result(name: str, addresses: Sequence[str]) -> DnsLookupResult:
    """
    Build a normalized success result dictionary.

    Args:
        name: DNS name that was resolved.
        addresses: Resolved IP address list.

    Returns:
        dict: Result payload with a stable schema.
    """
    return {
        "addrs": list(addresses),
        "error": False,
        "error_msg": "",
        "name": name,
    }


def dns_lookup(
    dns_name: Optional[str],
    timeout: Union[int, float] = 3,
    dns_resolvers: Optional[Sequence[str]] = None,
) -> DnsLookupResult:
    """
    Perform a DNS lookup and return a normalized dictionary result.

    The function uses dnspython's resolver with the configured timeout and
    optional explicit nameserver list. The returned dictionary always contains
    the keys ``addrs``, ``error``, ``error_msg``, and ``name``.

    Args:
        dns_name: DNS name to resolve.
        timeout: Resolver timeout and lifetime in seconds.
        dns_resolvers: Optional list of nameserver IP addresses.

    Returns:
        dict: Normalized lookup result.
    """
    resolver = Resolver()
    resolver.timeout = float(timeout)
    resolver.lifetime = float(timeout)

    normalized_name = dns_name.strip() if isinstance(dns_name, str) else dns_name

    if not normalized_name:
        return _error_result(
            normalized_name,
            "No DNS name for resolving given",
        )

    if dns_resolvers:
        resolver.nameservers = list(dns_resolvers)

    try:
        records = resolver.resolve(normalized_name)
        addresses: List[str] = [
            getattr(record, "address", record.to_text()) for record in records
        ]
        return _success_result(normalized_name, addresses)

    except dns.resolver.NXDOMAIN:
        return _error_result(normalized_name, "No such domain")

    except dns.resolver.NoAnswer:
        return _error_result(normalized_name, "No DNS answer received")

    except dns.resolver.NoNameservers as exc:
        return _error_result(normalized_name, repr(exc))

    except dns.resolver.Timeout:
        return _error_result(normalized_name, "Timed out while resolving")

    except dns.resolver.NameError as exc:
        return _error_result(normalized_name, repr(exc))

    except dns.exception.DNSException as exc:
        return _error_result(
            normalized_name,
            f"Unhandled exception ({repr(exc)})",
        )
