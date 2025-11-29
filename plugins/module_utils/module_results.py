#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0


def results(module, result_state):
    """
    # define changed for the running tasks

    input:
        list of dictionaries
        e.g.:
            [
                {'busybox-1': {'state': 'container.env, publisher.properties, busybox-1.properties successful written'}},
                {'hello-world-1': {'state': 'container.env, hello-world-1.properties successful written'}}
            ]
    return:
        tuple of ...
        (bool, bool, bool, dict, dict, dict)
    """

    # module.log(msg=f"{result_state}")

    combined_d = {key: value for d in result_state for key, value in d.items()}
    # find all changed and define our variable
    state = {
        k: v for k, v in combined_d.items() if isinstance(v, dict) if v.get("state")
    }
    changed = {
        k: v for k, v in combined_d.items() if isinstance(v, dict) if v.get("changed")
    }
    failed = {
        k: v for k, v in combined_d.items() if isinstance(v, dict) if v.get("failed")
    }

    _state = len(state) > 0
    _changed = len(changed) > 0
    _failed = len(failed) > 0

    # module.log(msg=f" - state   {_state} '{state}'")
    # module.log(msg=f" - changed {_changed} '{changed}'")
    # module.log(msg=f" - failed  {_failed} '{failed}'")

    return (_state, _changed, _failed, state, changed, failed)
