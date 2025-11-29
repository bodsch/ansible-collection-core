#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import datetime
import os


def cache_valid(
    module, cache_file_name, cache_minutes=60, cache_file_remove=True
) -> bool:
    """
    read local file and check the creation time against local time

    returns 'False' when cache are out of sync
    """
    out_of_cache = False

    if os.path.isfile(cache_file_name):
        module.debug(msg=f"read cache file '{cache_file_name}'")
        now = datetime.datetime.now()
        creation_time = datetime.datetime.fromtimestamp(
            os.path.getctime(cache_file_name)
        )
        diff = now - creation_time
        # define the difference from now to the creation time in minutes
        cached_time = diff.total_seconds() / 60
        out_of_cache = cached_time > cache_minutes

        module.debug(msg=f" - now            {now}")
        module.debug(msg=f" - creation_time  {creation_time}")
        module.debug(msg=f" - cached since   {cached_time}")
        module.debug(msg=f" - out of cache   {out_of_cache}")

        if out_of_cache and cache_file_remove:
            os.remove(cache_file_name)
    else:
        out_of_cache = True

    module.debug(msg="cache is {0}valid".format("not " if out_of_cache else ""))

    return out_of_cache
