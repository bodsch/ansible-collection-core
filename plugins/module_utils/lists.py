#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0


def find_in_list(list, value):
    """
    """
    for entry in list:
        for k, v in entry.items():
            if k == value:
                return entry

    return None


def compare_two_lists(list1: list, list2: list, debug=False):
    """
        Compare two lists and logs the difference.
        :param list1: first list.
        :param list2: second list.
        :return:      if there is difference between both lists.
    """
    debug_msg = []

    diff = [x for x in list2 if x not in list1]

    changed = not (len(diff) == 0)
    if debug:
        if not changed:
            debug_msg.append(f"There are {len(diff)} differences:")
            debug_msg.append(f"  {diff[:5]}")

    return changed, diff, debug_msg
