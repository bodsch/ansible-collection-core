#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            'type': self.var_type,
            'config_bool': self.config_bool_as_string,
        }

    def var_type(self, var):
        """
            Get the type of a variable
        """
        if isinstance(var, str) or type(var).__name__ == "AnsibleUnsafeText":
            return "str"

        return type(var).__name__

    def config_bool_as_string(self, data, true_as="yes", false_as="no"):
        """
            return string for boolean
        """
        # display.v(f"config_bool({data}, {type(data)}, {true_as}, {false_as})")

        result = false_as

        if isinstance(data, bool):
            result = true_as if data else false_as

        if type(data) is None:
            result = False
        elif type(data) is bool:
            result = true_as if data else false_as
        else:
            result = data

        return result
