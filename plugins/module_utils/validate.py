#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0


def validate(value, default=None):
    """
    """
    if value:
        if isinstance(value, str) or isinstance(value, list) or isinstance(value, dict):
            if len(value) > 0:
                return value

        if isinstance(value, int):
            return int(value)

        if isinstance(value, bool):
            return bool(value)

    return default
