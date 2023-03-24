#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

import os


def create_directory(dir):
    """
    """
    try:
        os.makedirs(dir, exist_ok=True)
    except FileExistsError:
        pass

    if os.path.isdir(dir):
        return True
    else:
        return False
