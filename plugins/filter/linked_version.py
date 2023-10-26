#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
__metaclass__ = type

from ansible.utils.display import Display
import os

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            'linked_version': self.linked_version,
        }

    def linked_version(self, data, install_path, version):
        """
            check for linked version in `install_path`
        """
        display.vvv(f"linked_version(self, {data}, {install_path}, {version})")

        _exists = data.get("exists", False)

        if _exists:
            _islink = data.get("islnk", False)
            _lnk_source = data.get("lnk_source", None)
            _path = data.get("path", None)

            if _lnk_source:
                _path = os.path.dirname(_lnk_source)

            display.vvv(f" - exists  : {_exists}")
            display.vvv(f" - is link : {_islink}")
            display.vvv(f" - link src: {_lnk_source}")
            display.vvv(f" - path    : {_path}")

            state = (install_path == _path)

            display.vv(f" - state    : {state}")

            return state
        else:
            return True
