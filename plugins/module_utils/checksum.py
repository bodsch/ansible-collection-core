#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import os
import json
import time
import hashlib


class Checksum():
    def __init__(self, module):
        self.module = module

    def checksum(self, plaintext, algorithm="sha256"):
        """
            compute checksum for plaintext
        """
        _data = self._harmonize_data(plaintext)

        checksum = hashlib.new(algorithm)
        checksum.update(_data.encode('utf-8'))

        return checksum.hexdigest()

    def validate(self, checksum_file, data=None):
        """
        """
        # self.module.log(msg=f" - checksum_file '{checksum_file}'")
        old_checksum = None

        if not isinstance(data, str) or not isinstance(data, dict):
            if not data and os.path.exists(checksum_file):
                os.remove(checksum_file)

        if os.path.exists(checksum_file):
            with open(checksum_file, "r") as f:
                old_checksum = f.readlines()[0]

        _data = self._harmonize_data(data)

        checksum = self.checksum(_data)
        changed = not (old_checksum == checksum)

        return (changed, checksum, old_checksum)

    def checksum_from_file(self, path, read_chunksize=65536, algorithm='sha256'):
        """
            Compute checksum of a file's contents.

        :param path: Path to the file
        :param read_chunksize: Maximum number of bytes to be read from the file
                                at once. Default is 65536 bytes or 64KB
        :param algorithm: The hash algorithm name to use. For example, 'md5',
                                'sha256', 'sha512' and so on. Default is 'sha256'. Refer to
                                hashlib.algorithms_available for available algorithms
        :return: Hex digest string of the checksum
        """

        if os.path.isfile(path):
            checksum = hashlib.new(algorithm)  # Raises appropriate exceptions.
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(read_chunksize), b''):
                    checksum.update(chunk)
                    # Release greenthread, if greenthreads are not used it is a noop.
                    time.sleep(0)

            return checksum.hexdigest()
        else:
            return None

    def write_checksum(self, checksum_file, checksum=None):
        """
        """
        with open(checksum_file, "w") as f:
            f.write(checksum)

    def _harmonize_data(self, data):
        """
        """
        if isinstance(data, dict):
            _data = json.dumps(data, sort_keys=True)

        if isinstance(data, list):
            _data = ''.join(str(x) for x in data)

        if isinstance(data, str):
            _data = data
        else:
            _data = data.copy()

        return _data
