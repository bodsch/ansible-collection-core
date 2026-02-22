#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

__metaclass__ = type

import os

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            "linked_version": self.linked_version,
        }

    def linked_version(self, data: dict, install_path: str, version: str):
        """
        check for linked version in `install_path`

            `data` are dictionary:
                {
                    'exists': True,
                    ''path': '/usr/bin/influxd', ...,
                    'islnk': True, ...,
                    'lnk_source': '/opt/influxd/2.8.0/influxd',
                    'lnk_target': '/opt/influxd/2.8.0/influxd', ...
                }
            `install_path`are string and NOT the filename!
                /opt/influxd/2.8.0


            result: TRUE, when destination is a link and the base path equal with install path
                    otherwise FALSE
        """
        display.vv(
            f"bodsch.core.linked_version(self, data: {data}, install_path: {install_path}, version: {version})"
        )

        _is_activated = False

        _destination_exists = data.get("exists", False)

        display.vvv(f" - destination exists  : {_destination_exists}")

        if _destination_exists:
            _destination_islink = data.get("islnk", False)
            _destination_lnk_source = data.get("lnk_source", None)
            _destination_path = data.get("path", None)

            if _destination_lnk_source:
                _destination_path = os.path.dirname(_destination_lnk_source)

            display.vvv(f"        - is link   : {_destination_islink}")
            display.vvv(f"        - link src  : {_destination_lnk_source}")
            display.vvv(f"        - base path : {_destination_path}")

            _is_activated = install_path == _destination_path

            # if not _is_activated:
            # display.vv(" - destination- and installation path are not qual.")

        #     display.vv(f" - state    : {state}")
        #
        #     return state
        # else:
        #     return True

        display.vv(f"= is activated: {_is_activated}")

        return _is_activated
