#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
from ansible.utils.display import Display

__metaclass__ = type
display = Display()


class FilterModule(object):
    def filters(self):
        return {
            'python_extra_args': self.python_extra_args
        }

    def python_extra_args(self, data, python_version, extra_args=[], break_system_packages=True):
        """
            add extra args for python pip installation
        """
        result = list(set(extra_args))

        python_version_major = python_version.get("major", None)
        python_version_minor = python_version.get("minor", None)

        if int(python_version_major) == 3 and int(python_version_minor) >= 11 and break_system_packages:
            result.append("--break-system-packages")

        # deduplicate
        result = list(set(result))

        result = " ".join(result)

        display.vv(f"= {result}")
        return result
