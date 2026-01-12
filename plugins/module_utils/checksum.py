#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import hashlib
import json
import os
import time
from typing import Any, Optional, Tuple

ChecksumValidationResult = Tuple[bool, str, Optional[str]]
ChecksumValidationFromFileResult = Tuple[bool, Optional[str], str]


class Checksum:
    """
    Helper class for calculating and validating checksums.

    This class is typically used in an Ansible-module context and keeps a reference
    to the calling module for optional logging.

    Attributes:
        module: An Ansible-like module object. Currently only stored for potential logging.
    """

    def __init__(self, module: Any) -> None:
        """
        Initialize the checksum helper.

        Args:
            module: An Ansible-like module instance.

        Returns:
            None
        """
        self.module = module

    def checksum(self, plaintext: Any, algorithm: str = "sha256") -> str:
        """
        Compute a checksum for arbitrary input data.

        The input is normalized via :meth:`_harmonize_data` and then hashed with
        the requested algorithm.

        Args:
            plaintext: Data to hash. Commonly a string, dict, or list.
            algorithm: Hashlib algorithm name (e.g. "md5", "sha256", "sha512").
                Defaults to "sha256".

        Returns:
            str: Hex digest of the computed checksum.

        Raises:
            ValueError: If the hash algorithm is not supported by hashlib.
            AttributeError: If the normalized value does not support ``encode("utf-8")``.
        """
        _data = self._harmonize_data(plaintext)
        checksum = hashlib.new(algorithm)
        checksum.update(_data.encode("utf-8"))

        return checksum.hexdigest()

    def validate(
        self, checksum_file: str, data: Any = None
    ) -> ChecksumValidationResult:
        """
        Validate (and optionally reset) a checksum file against given data.

        Behavior:
          - If ``data`` is ``None`` and ``checksum_file`` exists, the checksum file is removed.
          - If ``checksum_file`` exists, its first line is treated as the previous checksum.
          - A new checksum is computed from ``data`` and compared to the previous one.

        Args:
            checksum_file: Path to the checksum file holding a single checksum line.
            data: Input data to hash and compare. Can be string/dict/list or another type
                supported by :meth:`_harmonize_data`. If ``None``, the checksum file may be removed.

        Returns:
            tuple[bool, str, Optional[str]]: (changed, checksum, old_checksum)
                changed: True if the checksum differs from the stored value (or no stored value exists).
                checksum: Newly computed checksum hex digest.
                old_checksum: Previously stored checksum (first line), or ``None`` if not available.

        Raises:
            ValueError: If the hash algorithm used internally is unsupported.
            AttributeError: If the normalized data does not support ``encode("utf-8")``.
        """
        # self.module.log(msg=f" - checksum_file '{checksum_file}'")
        old_checksum: Optional[str] = None

        if not isinstance(data, str) or not isinstance(data, dict):
            # self.module.log(msg=f" - {type(data)} {len(data)}")
            if data is None and os.path.exists(checksum_file):
                os.remove(checksum_file)

        if os.path.exists(checksum_file):
            with open(checksum_file, "r") as f:
                old_checksum = f.readlines()[0].strip()

        _data = self._harmonize_data(data)
        checksum = self.checksum(_data)
        changed = not (old_checksum == checksum)

        return (changed, checksum, old_checksum)

    def validate_from_file(
        self, checksum_file: str, data_file: str
    ) -> ChecksumValidationFromFileResult:
        """
        Validate a checksum file against the contents of another file.

        Behavior:
          - If ``data_file`` does not exist but ``checksum_file`` exists, the checksum file is removed.
          - If ``checksum_file`` exists, its first line is treated as the previous checksum.
          - A checksum is computed from ``data_file`` and compared to the previous one.

        Args:
            checksum_file: Path to the checksum file holding a single checksum line.
            data_file: Path to the file whose contents should be hashed.

        Returns:
            tuple[bool, Optional[str], str]: (changed, checksum_from_file, old_checksum)
                changed: True if the checksum differs from the stored value.
                checksum_from_file: Hex digest checksum of ``data_file`` contents, or ``None`` if
                    ``data_file`` is not a file.
                old_checksum: Previously stored checksum (first line), or empty string if not available.
        """
        # self.module.log(msg=f" - checksum_file '{checksum_file}'")
        old_checksum = ""

        if not os.path.exists(data_file) and os.path.exists(checksum_file):
            """
            remove checksum_file, when data_file are removed
            """
            os.remove(checksum_file)

        if os.path.exists(checksum_file):
            with open(checksum_file, "r", encoding="utf-8") as f:
                old_checksum = f.readlines()[0].strip()

        checksum_from_file = self.checksum_from_file(data_file)
        changed = not (old_checksum == checksum_from_file)

        return (changed, checksum_from_file, old_checksum)

    def checksum_from_file(
        self,
        path: str,
        read_chunksize: int = 65536,
        algorithm: str = "sha256",
    ) -> Optional[str]:
        """
        Compute checksum of a file's contents.

        The file is read in chunks to avoid loading the full file into memory.
        A small ``time.sleep(0)`` is performed per chunk (noop in most cases).

        Args:
            path: Path to the file.
            read_chunksize: Maximum number of bytes read at once. Defaults to 65536 (64 KiB).
            algorithm: Hash algorithm name to use. Defaults to "sha256".

        Returns:
            Optional[str]: Hex digest string of the checksum if ``path`` is a file,
            otherwise ``None``.

        Raises:
            ValueError: If the hash algorithm is not supported by hashlib.
            OSError: If the file cannot be opened/read.
        """
        if os.path.isfile(path):
            checksum = hashlib.new(algorithm)  # Raises appropriate exceptions.
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(read_chunksize), b""):
                    checksum.update(chunk)
                    # Release greenthread, if greenthreads are not used it is a noop.
                    time.sleep(0)

            return checksum.hexdigest()

        return None

    def write_checksum(self, checksum_file: str, checksum: Any) -> None:
        """
        Write a checksum value to disk (single line with trailing newline).

        Args:
            checksum_file: Destination path for the checksum file.
            checksum: Checksum value to write. Only written if it is truthy and its string
                representation is not empty.

        Returns:
            None

        Raises:
            OSError: If the file cannot be opened/written.
        """
        if checksum and len(str(checksum)) != 0:
            with open(checksum_file, "w", encoding="utf-8") as f:
                f.write(checksum + "\n")

    def _harmonize_data(self, data: Any) -> Any:
        """
        Normalize data into a stable representation for hashing.

        Rules:
          - dict: JSON serialized with sorted keys
          - list: Concatenation of stringified elements
          - str: returned as-is
          - other: returns ``data.copy()``

        Args:
            data: Input data.

        Returns:
            Any: Normalized representation. For typical input types (dict/list/str) this
            is a string. For other types, the return value depends on ``data.copy()``.

        Raises:
            AttributeError: If ``data`` is not dict/list/str and does not implement ``copy()``.
            TypeError: If JSON serialization fails for dictionaries.
        """
        # self.module.log(msg=f" - type before:  '{type(data)}'")
        if isinstance(data, dict):
            _data = json.dumps(data, sort_keys=True)
        elif isinstance(data, list):
            _data = "".join(str(x) for x in data)
        elif isinstance(data, str):
            _data = data
        else:
            _data = data.copy()

        # self.module.log(msg=f" - type after :  '{type(_data)}'")
        return _data
