# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()

"""
Diese Funktion geht rekursiv durch die Struktur (ob Dictionary oder Liste) und entfernt alle Einträge,
die entweder None, einen leeren String, ein leeres Dictionary, eine leere Liste enthalten.

Für Dictionaries wird jedes Schlüssel-Wert-Paar überprüft, und es wird nur gespeichert, wenn der Wert nicht leer ist.
Für Listen werden nur nicht-leere Elemente in das Ergebnis aufgenommen.

Es wurde eine Hilfsfunktion `is_empty` eingeführt, die überprüft, ob ein Wert als "leer" betrachtet werden soll.

Diese Funktion berücksichtigt nun explizit, dass boolesche Werte (True und False) nicht als leer betrachtet werden, sondern erhalten bleiben.
In der is_empty-Funktion wurde eine Überprüfung hinzugefügt, um sicherzustellen, dass die Zahl 0 nicht als leer betrachtet wird.
Wenn der Wert 0 ist, wird er beibehalten.
"""


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'remove_empty_values': self.remove_empty_values,
        }

    def remove_empty_values(self, data):
        display.v(f"remove_empty_values(self, {data})")

        def is_empty(value):
            """Überprüfen, ob der Wert leer ist (ignoriere boolesche Werte)."""
            if isinstance(value, bool):
                return False  # Boolesche Werte sollen erhalten bleiben
            if value == 0:
                return False  # Zahl 0 soll erhalten bleiben

            return value in [None, '', {}, [], False]

        if isinstance(data, dict):
            # Durch alle Schlüssel-Wert-Paare iterieren
            return {key: self.remove_empty_values(value) for key, value in data.items() if not is_empty(value)}
        elif isinstance(data, list):
            # Leere Listen und leere Elemente entfernen
            return [self.remove_empty_values(item) for item in data if not is_empty(item)]
        else:
            # Andere Typen direkt zurückgeben (einschließlich boolesche Werte)
            return data
