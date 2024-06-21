#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from jinja2 import Template
import json

# from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum


class TemplateHandler:
    """
    """

    def __init__(self, module):
        self.module = module

    def write_template(self, file_name, template, data):
        """
        """
        if isinstance(data, dict):
            """
                sort data
            """
            data = json.dumps(data, sort_keys=True)
            if isinstance(data, str):
                data = json.loads(data)

        if isinstance(data, list):
            data = ":".join(data)

        tm = Template(template, trim_blocks=True, lstrip_blocks=True)
        d = tm.render(item=data)

        with open(file_name, "w") as f:
            f.write(d)

    def write_when_changed(self, tmp_file, data_file, **kwargs):
        """
        """
        self.module.log(f"write_when_changed(self, {tmp_file}, {data_file}, {kwargs})")

        # checksum = Checksum(self.module)

        return None


# OBSOLETE, BUT STILL SUPPORTED FOR COMPATIBILITY REASONS
def write_template(file_name, template, data):
    """
    """
    if isinstance(data, dict):
        """
            sort data
        """
        data = json.dumps(data, sort_keys=True)
        if isinstance(data, str):
            data = json.loads(data)

    if isinstance(data, list):
        data = ":".join(data)

    tm = Template(template, trim_blocks=True, lstrip_blocks=True)
    d = tm.render(item=data)

    with open(file_name, "w") as f:
        f.write(d)
