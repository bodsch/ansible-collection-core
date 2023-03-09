#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from jinja2 import Template
import json


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

    tm = Template(template)
    d = tm.render(item=data)

    with open(file_name, "w") as f:
        f.write(d)
