#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2024, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, print_function

__metaclass__ = type

import os

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """ """

    def filters(self):
        return {
            "support_tls": self.support_tls,
            "tls_directory": self.tls_directory,
        }

    def support_tls(self, data):
        """
        collabora_config:
          ssl:
            enabled: true
            cert_file: /etc/coolwsd/cert.pem
            key_file: /etc/coolwsd/key.pem
            ca_file: /etc/coolwsd/ca-chain.cert.pem
          storage:
            ssl:
              enabled: ""
              cert_file: /etc/coolwsd/cert.pem
              key_file: /etc/coolwsd/key.pem
              ca_file: /etc/coolwsd/ca-chain.cert.pem
        """
        display.v(f"support_tls({data})")

        ssl_data = data.get("ssl", {})

        ssl_enabled = ssl_data.get("enabled", None)
        ssl_ca = ssl_data.get("ca_file", None)
        ssl_cert = ssl_data.get("cert_file", None)
        ssl_key = ssl_data.get("key_file", None)

        if ssl_enabled and ssl_ca and ssl_cert and ssl_key:
            return True
        else:
            return False

    def tls_directory(self, data):
        """ """
        display.v(f"tls_directory({data})")

        directory = []

        ssl_data = data.get("ssl", {})

        ssl_ca = ssl_data.get("ca_file", None)
        ssl_cert = ssl_data.get("cert_file", None)
        ssl_key = ssl_data.get("key_file", None)

        if ssl_ca and ssl_cert and ssl_key:
            directory.append(os.path.dirname(ssl_ca))
            directory.append(os.path.dirname(ssl_cert))
            directory.append(os.path.dirname(ssl_key))

        directory = list(set(directory))

        if len(directory) == 1:
            result = directory[0]

        display.v(f" = {result}")

        return result
