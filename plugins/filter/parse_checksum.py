#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
__metaclass__ = type

import re
from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            'parse_checksum': self.parse_checksum,
        }

    def parse_checksum(self, data, application, os, arch, file_extension="tar.gz"):
        """
            parse version string
        """
        display.vvv(f"parse_checksum(self, data, {application}, {os}, {arch})")

        checksum = None
        os = os.lower()
        display.vvv(f" data: {data}")
        display.vvv(f" os: {os}")
        display.vvv(f" arch: {arch}")
        display.vvv(f" file_extension: {file_extension}")

        if isinstance(data, list):
            # 206cf787c01921574ca171220bb9b48b043c3ad6e744017030fed586eb48e04b  alertmanager-0.25.0.linux-amd64.tar.gz
            # (?P<checksum>[a-zA-Z0-9]+).*alertmanager[-_].*linux-amd64\.tar\.gz$
            checksum = [x for x in data if re.search(fr"(?P<checksum>[a-zA-Z0-9]+).*{application}[-_].*{os}[-_]{arch}\.{file_extension}", x)][0]

            display.vvv(f"  found checksum: {checksum}")

        if isinstance(checksum, str):
            checksum = checksum.split(" ")[0]

        display.vv(f"= checksum: {checksum}")

        return checksum
