#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            "union_by": self.union,
        }

    def union(self, data, defaults, union_by):
        """
        union by ..
        """
        result = []

        if len(data) == 0:
            result = defaults
        else:
            for i in data:
                display.vv(f"  - {i}")
                x = i.get(union_by, None)

                if x:
                    found = [d for d in defaults if d.get(union_by) == x]

                    if found:
                        result.append(i)
                    else:
                        result.append(found[0])
                else:
                    result.append(i)

        display.vv(f"= {result}")
        return result
