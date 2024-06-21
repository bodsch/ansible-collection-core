#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
from ansible.utils.display import Display
from ansible_collections.bodsch.core.plugins.module_utils.dns_lookup import dns_lookup

__metaclass__ = type
display = Display()


class FilterModule(object):
    def filters(self):
        return {
            'dns_lookup': self.lookup
        }

    def lookup(self, dns_name, timeout=3, dns_resolvers=["9.9.9.9"]):
        """
          use a simple DNS lookup, return results in a dictionary

          similar to
          {'addrs': [], 'error': True, 'error_msg': 'No such domain instance', 'name': 'instance'}
        """
        display.vvv(f"lookup({dns_name}, {timeout}, {dns_resolvers})")

        result = dns_lookup(dns_name, timeout, dns_resolvers)

        display.vv(f"= return : {result}")

        return result
