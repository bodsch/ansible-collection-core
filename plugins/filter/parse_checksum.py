#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, annotations, division, print_function

import re
from collections.abc import Callable

from ansible.errors import AnsibleFilterError  # type: ignore[import-untyped]
from ansible.utils.display import Display  # type: ignore[import-untyped]

__metaclass__ = type

display = Display()

DOCUMENTATION = r"""
---
module: parse_checksum
version_added: "1.0.0"
author:
  - "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Extract a checksum for a specific binary from a checksum list.
description:
  - Parses a list of checksum lines (as typically published alongside release
    artifacts) and returns the hex checksum that matches the given application,
    operating system, architecture, and file extension.
  - Each line in the input list is expected to follow the format
    C(<hex_checksum>  <filename>) (two spaces between checksum and filename).
  - The filter uses a regex to locate the matching entry and returns only the
    hex digest portion.

notes:
  - The filter is exposed as C(parse_checksum).
  - If no matching line is found, an C(AnsibleFilterError) is raised.

options:
  data:
    description:
      - List of checksum lines to search through.
    type: list
    elements: str
    required: true
  application:
    description:
      - Name of the application/binary to match in the filename portion.
    type: str
    required: true
  os:
    description:
      - Target operating system (e.g. C(linux), C(darwin)).
      - The value is compared case-insensitively.
    type: str
    required: true
  arch:
    description:
      - Target CPU architecture (e.g. C(amd64), C(arm64)).
    type: str
    required: true
  file_extension:
    description:
      - Expected file extension of the artifact.
      - If omitted, the extension is not considered during matching.
    type: str
    required: false
"""

EXAMPLES = r"""
- name: Download checksum file
  ansible.builtin.uri:
    url: "https://github.com/prometheus/alertmanager/releases/download/v0.25.0/sha256sums.txt"
    return_content: true
  register: checksum_file

- name: Extract checksum for linux-amd64 tarball
  ansible.builtin.set_fact:
    alertmanager_checksum: >-
      {{ checksum_file.content.split('\n')
         | bodsch.core.parse_checksum('alertmanager', 'linux', 'amd64') }}
"""

RETURN = r"""
_value:
  description:
    - The hex checksum string matching the requested artifact.
  type: str
  returned: always
  sample: "206cf787c01921574ca171220bb9b48b043c3ad6e744017030fed586eb48e04b"
"""


class FilterModule(object):
    """Ansible filter plugin to extract checksums from checksum file listings."""

    def filters(self) -> dict[str, Callable[..., str]]:
        """Return the filter mapping exposed to Ansible.

        Returns:
            dict: Mapping of filter names to callables.
        """
        return {
            "parse_checksum": self.parse_checksum,
        }

    def parse_checksum(
        self,
        data: list[str],
        application: str,
        os: str,
        arch: str,
        file_extension: str | None = None,
    ) -> str:
        """Extract the checksum for a specific artifact from a list of checksum lines.

        Args:
            data: List of checksum lines, each formatted as
                ``<hex_checksum>  <filename>``.
            application: Application name to match in the filename.
            os: Target operating system (matched case-insensitively).
            arch: Target CPU architecture.
            file_extension: Expected file extension of the artifact.
                If ``None``, the extension is not considered during matching.

        Returns:
            The hex checksum string for the matching artifact.

        Raises:
            AnsibleFilterError: If *data* is not a list or no matching entry
                is found.
        """
        display.vv(
            f"bodsch.core.parse_checksum(data, {application}, {os}, {arch}, {file_extension})"
        )

        if not isinstance(data, list):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise AnsibleFilterError(  # pyright: ignore[reportUnreachable]
                f"parse_checksum expects a list as input, got {type(data).__name__}"
            )

        os_lower = os.lower()
        # Escape user-provided strings to prevent regex injection
        app_escaped = re.escape(application)
        os_escaped = re.escape(os_lower)
        arch_escaped = re.escape(arch)

        if file_extension:
            ext_escaped = re.escape(file_extension)
            pattern = re.compile(
                rf"^(?P<checksum>[0-9a-fA-F]+)\s+.*{app_escaped}[-_].*{os_escaped}[-_]{arch_escaped}.*\.{ext_escaped}$"
            )
        else:
            pattern = re.compile(
                rf"^(?P<checksum>[0-9a-fA-F]+)\s+.*{app_escaped}[-_].*{os_escaped}[-_]{arch_escaped}$"
            )

        display.vvv(f"  pattern: {pattern.pattern}")
        display.vvv(f"  os: {os_lower}")
        display.vvv(f"  arch: {arch}")
        display.vvv(f"  file_extension: {file_extension}")

        for line in data:
            match = pattern.search(line)
            if match:
                checksum = match.group("checksum")
                display.vv(f"= checksum: {checksum}")
                return checksum

        ext_info = f".{file_extension}" if file_extension else ""
        raise AnsibleFilterError(
            f"parse_checksum: no matching checksum found for {application}-*{os_lower}-{arch}*{ext_info}"
        )
