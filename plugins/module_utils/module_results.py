#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

ResultEntry = Dict[str, Dict[str, Any]]
ResultState = Iterable[ResultEntry]

ResultsReturn = Tuple[
    bool,  # has_state
    bool,  # has_changed
    bool,  # has_failed
    Dict[str, Dict[str, Any]],  # state
    Dict[str, Dict[str, Any]],  # changed
    Dict[str, Dict[str, Any]],  # failed
]


def results(module: Any, result_state: ResultState) -> ResultsReturn:
    """
    Aggregate per-item module results into combined state/changed/failed maps.

    The function expects an iterable of dictionaries, where each dictionary maps
    an item identifier (e.g. a container name) to a dict containing optional keys
    like ``state``, ``changed``, and ``failed``.

    Example input:
        [
            {"busybox-1": {"state": "container.env written", "changed": True}},
            {"hello-world-1": {"state": "hello-world-1.properties written"}},
            {"nginx-1": {"failed": True, "msg": "..." }}
        ]

    Args:
        module: An Ansible-like module object. Currently unused (kept for API symmetry
            and optional debugging/logging).
        result_state: Iterable of per-item result dictionaries as described above.

    Returns:
        tuple[bool, bool, bool, dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
            (has_state, has_changed, has_failed, state, changed, failed)

            has_state:
                True if at least one item dict contains a truthy ``"state"`` key.
            has_changed:
                True if at least one item dict contains a truthy ``"changed"`` key.
            has_failed:
                True if at least one item dict contains a truthy ``"failed"`` key.
            state:
                Mapping of item_id -> item_dict for all items with a truthy ``"state"``.
            changed:
                Mapping of item_id -> item_dict for all items with a truthy ``"changed"``.
            failed:
                Mapping of item_id -> item_dict for all items with a truthy ``"failed"``.

    Notes:
        If the same item_id appears multiple times in ``result_state``, later entries
        overwrite earlier ones during the merge step.
    """

    # module.log(msg=f"{result_state}")

    combined_d: Dict[str, Dict[str, Any]] = {
        key: value for d in result_state for key, value in d.items()
    }

    state: Dict[str, Dict[str, Any]] = {
        k: v for k, v in combined_d.items() if isinstance(v, dict) and v.get("state")
    }
    changed: Dict[str, Dict[str, Any]] = {
        k: v for k, v in combined_d.items() if isinstance(v, dict) and v.get("changed")
    }
    failed: Dict[str, Dict[str, Any]] = {
        k: v for k, v in combined_d.items() if isinstance(v, dict) and v.get("failed")
    }

    has_state = len(state) > 0
    has_changed = len(changed) > 0
    has_failed = len(failed) > 0

    return (has_state, has_changed, has_failed, state, changed, failed)
