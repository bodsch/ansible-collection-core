#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os
import time
import hashlib

class Checksum():
    """
    """

    def __init__(self, module):
        """
        """
        self.module = module

    def checksum(self, algorithm="sha256", plaintext):
        """
            compute checksum for plaintext
        """
        checksum = hashlib.new(algorithm)
        checksum.update(plaintext.encode('utf-8'))

        return checksum.hexdigest()


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
