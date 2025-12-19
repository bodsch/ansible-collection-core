#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

__metaclass__ = type

# filter_plugins/var_type.py
from collections.abc import Mapping, Sequence
from collections.abc import Set as ABCSet

from ansible.utils.display import Display

# optional: we vermeiden harte Abhängigkeit von Ansible, behandeln aber deren Wrapper als str
_STR_WRAPPERS = {"AnsibleUnsafeText", "AnsibleUnicode", "AnsibleVaultEncryptedUnicode"}

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            "type": self.var_type,
            "config_bool": self.config_bool_as_string,
            "string_to_list": self.string_to_list,
        }

    def var_type(self, value):
        """
        Liefert kanonische Python-Typnamen: str, int, float, bool, list, tuple, set, dict, NoneType.
        Fällt bei fremden/Wrapper-Typen auf die jeweilige ABC-Kategorie zurück.
        """
        # None
        if value is None:
            return "NoneType"

        t = type(value)

        # String-ähnliche Wrapper (z.B. AnsibleUnsafeText)
        if isinstance(value, str) or t.__name__ in _STR_WRAPPERS:
            return "string"

        # Bytes
        if isinstance(value, bytes):
            return "bytes"
        if isinstance(value, bytearray):
            return "bytearray"

        # Bool vor int (bool ist Subklasse von int)
        if isinstance(value, bool):
            return "bool"

        # Grundtypen
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"

        # Konkrete eingebaute Container zuerst
        if isinstance(value, list):
            return "list"
        if isinstance(value, tuple):
            return "tuple"
        if isinstance(value, set):
            return "set"
        if isinstance(value, dict):
            return "dict"

        # ABC-Fallbacks für Wrapper (z.B. _AnsibleLazyTemplateList, AnsibleMapping ...)
        if isinstance(value, Mapping):
            return "dict"
        if isinstance(value, ABCSet):
            return "set"
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            # Unbekannte sequenzartige Wrapper -> als list behandeln
            return "list"

        # Letzter Ausweg: konkreter Klassenname
        return t.__name__

    def config_bool_as_string(self, data, true_as="yes", false_as="no"):
        """
        return string for boolean
        """
        # display.vv(f"bodsch.core.config_bool({data}, {type(data)}, {true_as}, {false_as})")

        result = false_as

        if isinstance(data, bool):
            result = true_as if data else false_as

        if type(data) is None:
            result = False
        elif type(data) is bool:
            result = true_as if data else false_as
        else:
            result = data

        return result

    def string_to_list(self, data):
        """ """
        display.vv(f"bodsch.core.string_to_list({data})")

        result = []
        if isinstance(data, str):
            result.append(data)
        elif isinstance(data, int):
            result.append(str(data))
        elif isinstance(data, list):
            result = data

        display.vv(f"= result: {result}")

        return result
