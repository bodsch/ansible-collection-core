#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

import os


def create_link(source, destination, force=False):
    """
        create a link ..
    """
    if force:
        os.remove(destination)
        os.symlink(source, destination)
    else:
        os.symlink(source, destination)


def remove_file(file_name):
    """
    """
    if os.path.exists(file_name):
        os.remove(file_name)
        return True

    return False
