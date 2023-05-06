#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
    """
    def filters(self):
        return {
            'union': self.union,
        }

    def union(self, data, list):
        """
        """
        result = []

        for i in data:
            name = i.get("name")
            display.vv(f"  - {name}")

            found = [d for d in list if d.get("name") == name]

            if found:
                result.append(i)
            else:
                result.append(found[0])

        display.vv(f"= {result}")
        return result
