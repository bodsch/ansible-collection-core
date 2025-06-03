#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import difflib
import itertools
import textwrap
import typing
from pathlib import Path


class SideBySide:
    """
    Erlaubt nebeneinanderstehende Vergleiche (Side‐by‐Side) von zwei Text-Versionen.
    Jetzt mit Ausgabe der Zeilennummern bei Änderungen.
    """

    def __init__(
        self,
        module,
        left: typing.Union[str, dict, typing.List[str]],
        right: typing.Union[str, dict, typing.List[str]],
    ):
        """
        :param module: Objekt mit einer .log(...)‐Methode zum Debuggen
        :param left:  Ursprünglicher Text (dict, String oder Liste von Zeilen)
        :param right: Neuer Text (dict, String oder Liste von Zeilen)
        """
        self.module = module
        self.default_separator = " | "
        self.left = self._normalize_input(left)
        self.right = self._normalize_input(right)

    @staticmethod
    def _normalize_input(
        data: typing.Union[str, dict, typing.List[str]]
    ) -> typing.List[str]:
        """
        Konvertiert dict → JSON‐String, String → Liste von Zeilen (splitlines),
        Liste bleibt unverändert (kopiert).
        """
        if isinstance(data, dict):
            data = json.dumps(data, indent=2)
        if isinstance(data, str):
            return data.splitlines()
        if isinstance(data, list):
            return data.copy()
        raise TypeError(f"Erwartet dict, str oder List[str], nicht {type(data)}")

    @staticmethod
    def _wrap_and_flatten(
        lines: typing.List[str], width: int
    ) -> typing.List[str]:
        """
        Wrappt jede Zeile auf maximal `width` Zeichen und flacht verschachtelte Listen ab.
        Leere Zeilen bleiben als [""] erhalten.
        """
        wrapper = textwrap.TextWrapper(
            width=width,
            break_long_words=False,
            replace_whitespace=False,
        )
        flat: typing.List[str] = []
        for line in lines:
            wrapped = wrapper.wrap(line)
            if not wrapped:
                # Wenn wrapper.wrap("") → [] → wir wollen [""] erhalten
                flat.append("")
            else:
                flat.extend(wrapped)
        return flat

    def side_by_side(
        self,
        left: typing.List[str],
        right: typing.List[str],
        width: int = 78,
        as_string: bool = False,
        separator: typing.Optional[str] = None,
        left_title: typing.Optional[str] = None,
        right_title: typing.Optional[str] = None,
    ) -> typing.Union[str, typing.List[str]]:
        """
        Gibt nebeneinanderstehende Zeilen zurück:
          [Links-Text][Padding][separator][Rechts-Text]

        :param left: Liste von Zeilen (bereits nummeriert/aufbereitet)
        :param right: Liste von Zeilen (bereits nummeriert/aufbereitet)
        :param width: Maximale Gesamtbreite (inkl. Separator)
        :param as_string: True → Rückgabe als einziger String mit "\n"
        :param separator: String, der links und rechts trennt (Default " | ")
        :param left_title: Überschrift ganz oben links (optional)
        :param right_title: Überschrift ganz oben rechts (optional)
        :return: Entweder List[str] oder ein einziger String
        """
        sep = separator or self.default_separator
        # Berechne, wie viele Zeichen pro Seite bleiben:
        side_width = (width - len(sep) - (1 - width % 2)) // 2

        # Wrap/flatten beide Seiten
        left_wrapped = self._wrap_and_flatten(left, side_width)
        right_wrapped = self._wrap_and_flatten(right, side_width)

        # Paare bilden, fehlende Zeilen mit leerem String auffüllen
        pairs = list(itertools.zip_longest(left_wrapped, right_wrapped, fillvalue=""))

        # Falls Überschriften angegeben, voranstellen (einschließlich Unterstreichung)
        if left_title or right_title:
            lt = left_title or ""
            rt = right_title or ""
            underline = "-" * side_width
            header = [(lt, rt), (underline, underline)]
            pairs = header + pairs

        # Jetzt jede Zeile zusammenbauen
        lines: typing.List[str] = []
        for l_line, r_line in pairs:
            l_text = l_line or ""
            r_text = r_line or ""
            pad = " " * max(0, side_width - len(l_text))
            lines.append(f"{l_text}{pad}{sep}{r_text}")

        return "\n".join(lines) if as_string else lines

    def better_diff(
        self,
        left: typing.Union[str, typing.List[str]],
        right: typing.Union[str, typing.List[str]],
        width: int = 78,
        as_string: bool = True,
        separator: typing.Optional[str] = None,
        left_title: typing.Optional[str] = None,
        right_title: typing.Optional[str] = None,
    ) -> typing.Union[str, typing.List[str]]:
        """
        Gibt einen Side-by-Side-Diff mit Markierung von gleichen/entfernten/hinzugefügten Zeilen
        und zusätzlich mit den Zeilennummern in den beiden Input-Dateien.

        Syntax der Prefixe:
          "  " → Zeile vorhanden in beiden Dateien
          "- " → Zeile nur in der linken Datei
          "+ " → Zeile nur in der rechten Datei
          "? " → wird komplett ignoriert

        Die Ausgabe hat Form:
          <LNr>: <Linke-Zeile>  |  <RNr>: <Rechte-Zeile>
        bzw. bei fehlender link/rechts-Zeile:
          <LNr>: <Linke-Zeile>  |       -
          -      |  <RNr>: <Rechte-Zeile>

        :param left: Ursprungstext als String oder Liste von Zeilen
        :param right: Vergleichstext als String oder Liste von Zeilen
        :param width: Gesamtbreite inkl. Separator
        :param as_string: True, um einen einzelnen String zurückzubekommen
        :param separator: Trenner (Standard: " | ")
        :param left_title: Überschrift links (optional)
        :param right_title: Überschrift rechts (optional)
        :return: Side-by-Side-Liste oder einzelner String
        """
        # 1) Ausgangsdaten normalisieren
        l_lines = left.splitlines() if isinstance(left, str) else left.copy()
        r_lines = right.splitlines() if isinstance(right, str) else right.copy()

        # 2) Differenz-Berechnung
        differ = difflib.Differ()
        diffed = list(differ.compare(l_lines, r_lines))

        # 3) Zähler für Zeilennummern
        left_lineno = 1
        right_lineno = 1

        left_side: typing.List[str] = []
        right_side: typing.List[str] = []

        # 4) Durchlaufe alle Diff‐Einträge
        for entry in diffed:
            code = entry[:2]   # "  ", "- ", "+ " oder "? "
            content = entry[2:]  # Der eigentliche Text

            if code == "  ":
                # Zeile existiert in beiden Dateien
                # Linke Seite: "  <LNr>: <Text>"
                # Rechte Seite: "  <RNr>: <Text>"
                left_side.append(f"{left_lineno:>4}: {content}")
                right_side.append(f"{right_lineno:>4}: {content}")
                left_lineno += 1
                right_lineno += 1

            elif code == "- ":
                # Nur in der linken Datei
                left_side.append(f"{left_lineno:>4}: {content}")
                # Rechts ein Platzhalter "-" ohne Nummer
                right_side.append("    -")
                left_lineno += 1

            elif code == "+ ":
                # Nur in der rechten Datei
                # Links wird ein "+" angezeigt, ohne LNr
                left_side.append("    +")
                right_side.append(f"{right_lineno:>4}: {content}")
                right_lineno += 1

            # "? " ignorieren wir komplett

        # 5) Nun übergeben wir die nummerierten Zeilen an side_by_side()
        return self.side_by_side(
            left=left_side,
            right=right_side,
            width=width,
            as_string=as_string,
            separator=separator,
            left_title=left_title,
            right_title=right_title,
        )

    def diff(
        self,
        width: int = 78,
        as_string: bool = True,
        separator: typing.Optional[str] = None,
        left_title: typing.Optional[str] = None,
        right_title: typing.Optional[str] = None,
    ) -> typing.Union[str, typing.List[str]]:
        """
        Führt better_diff() für die in __init__ geladenen left/right‐Strings aus.

        :param width: Gesamtbreite inkl. Separator
        :param as_string: True, um einen einzelnen String zurückzubekommen
        :param separator: Trenner (Standard: " | ")
        :param left_title: Überschrift links (optional)
        :param right_title: Überschrift rechts (optional)

        :return: Side-by-Side-Liste oder einzelner String
        """
        return self.better_diff(
            left=self.left,
            right=self.right,
            width=width,
            as_string=as_string,
            separator=separator,
            left_title=left_title,
            right_title=right_title,
        )

    def diff_between_files(
        self,
        file_1: typing.Union[str, Path],
        file_2: typing.Union[str, Path],
    ) -> typing.Union[str, typing.List[str]]:
        """
        Liest zwei Dateien ein und liefert ihren Side-by-Side‐Diff (mit Zeilennummern).

        :param file_1: Pfad zur ersten Datei
        :param file_2: Pfad zur zweiten Datei
        :return: Liste der formatierten Zeilen oder einziger String (as_string=True)
        """
        f1 = Path(file_1)
        f2 = Path(file_2)

        self.module.log(f"diff_between_files({f1}, {f2})")

        if not f1.is_file() or not f2.is_file():
            self.module.log(f"  Eine oder beide Dateien existieren nicht: {f1}, {f2}")
            # Hier geben wir für den Fall „Datei fehlt“ einfach einen leeren String zurück.
            return ""

        # Dateien in Listen von Zeilen einlesen (ohne trailing "\n")
        old_lines = f1.read_text(encoding="utf-8").splitlines()
        new_lines = f2.read_text(encoding="utf-8").splitlines()

        self.module.log(f"  Gelesen: {len(old_lines)} Zeilen aus {f1}")
        self.module.log(f"  Gelesen: {len(new_lines)} Zeilen aus {f2}")

        diffed = self.better_diff(
            left=old_lines,
            right=new_lines,
            width=140,
            as_string=True,
            separator=self.default_separator,
            left_title="  Original",
            right_title="  Update",
        )

        # Nur einen Auszug fürs Logging (z.B. erste 200 Zeichen)
        self.module.log(f"  diffed output (gekürzt):\n{diffed[:200]}...")
        return diffed
