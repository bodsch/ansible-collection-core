#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
binary_deploy_remote.py

Remote worker module for the binary_deploy action plugin.
This module expects that src_dir (when copy=true) is available on the remote host.
"""

from __future__ import annotations

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.versioned_deployment import (
    BinaryDeploy,
)


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "install_dir": {"type": "path", "required": True},
            "link_dir": {"type": "path", "default": "/usr/bin"},
            "src_dir": {"type": "path", "required": False},
            "copy": {"type": "bool", "default": True},
            "items": {"type": "list", "elements": "dict", "required": True},
            "activation_name": {"type": "str", "required": False},
            "owner": {"type": "str", "required": False},
            "group": {"type": "str", "required": False},
            "mode": {"type": "str", "default": "0755"},
            "cleanup_on_failure": {"type": "bool", "default": True},
            "check_only": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )

    BinaryDeploy(module).run()


if __name__ == "__main__":
    main()
