#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021-2026, Bodo Schulz <me+ansible@bodsch.me>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible filter plugin prepare a list of directories for `bodsch.core.directories`.
"""

from __future__ import annotations

from typing import Any

from ansible.utils.display import Display

display = Display()


class FilterModule:
    """
    """

    @staticmethod
    def filters() -> dict[str, Any]:
        return {
            "directory_path": FilterModule.directory_path,
        }

    @classmethod
    def directory_path(
        cls,
        data: list[str],
    ) -> list[dict[str, str]]:
        """
        Extract cache directory paths from nginx cache definitions.

        Input example:
            ['/var/log/nextcloud', '/var/www/nc_data']

        Output example:
            [
                {'path': '/var/log/nextcloud'},
                {'path': '/var/www/nc_data'}
            ]

        Args:
            data:
                List of cache configuration dictionaries.

        Returns:
            List of dictionaries containing only the cache path.
        """
        display.vv(
            f"bodsch.core.directory_path(data={data})"
        )

        if not isinstance(data, list):
            raise TypeError(
                "directory_path expects a list of dictionaries."
            )

        result = cls._extract_paths(data)

        display.vv(
            f"bodsch.core.directory_path(result={result})"
        )

        return result

    @staticmethod
    def _extract_paths(
        data: list[str],
    ) -> list[dict[str, str]]:
        """
        Extract valid path entries from input data.

        Args:
            data:
                Source cache configuration list.

        Returns:
            Normalized path dictionaries.
        """
        return [{"path": item} for item in data]
