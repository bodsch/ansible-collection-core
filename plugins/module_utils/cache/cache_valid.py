#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import datetime
import os
from pathlib import Path
from typing import Any


def cache_valid_old(
    module, cache_file_name, cache_minutes=60, cache_file_remove=True
) -> bool:
    """
    read local file and check the creation time against local time

    returns 'False' when cache are out of sync
    """
    out_of_cache = False

    if os.path.isfile(cache_file_name):
        module.debug(msg=f"read cache file '{cache_file_name}'")
        now = datetime.datetime.now()
        creation_time = datetime.datetime.fromtimestamp(
            os.path.getctime(cache_file_name)
        )
        diff = now - creation_time
        # define the difference from now to the creation time in minutes
        cached_time = diff.total_seconds() / 60
        out_of_cache = cached_time > cache_minutes

        module.debug(msg=f" - now            {now}")
        module.debug(msg=f" - creation_time  {creation_time}")
        module.debug(msg=f" - cached since   {cached_time}")
        module.debug(msg=f" - out of cache   {out_of_cache}")

        if out_of_cache and cache_file_remove:
            os.remove(cache_file_name)
    else:
        out_of_cache = True

    module.debug(msg="cache is {0}valid".format("not " if out_of_cache else ""))

    return out_of_cache


def cache_valid(
    module: Any,
    cache_file_name: str,
    cache_minutes: int = 60,
    cache_file_remove: bool = True,
) -> bool:
    """
    Prüft, ob eine Cache-Datei älter als `cache_minutes` ist oder gar nicht existiert.

    Gibt True zurück, wenn der Cache abgelaufen ist (oder nicht existiert) und
    ggf. gelöscht wurde (wenn cache_file_remove=True). Sonst False.

    :param module: Ansible-Modulobjekt, um Debug-Logs zu schreiben.
    :param cache_file_name: Pfad zur Cache-Datei (String).
    :param cache_minutes: Maximales Alter in Minuten, danach gilt der Cache als ungültig.
    :param cache_file_remove: Ob abgelaufene Cache-Datei gelöscht werden soll.
    """
    path = Path(cache_file_name)

    # Existiert die Datei nicht? → Cache gilt sofort als ungültig
    if not path.is_file():
        module.debug(msg=f"Cache-Datei '{cache_file_name}' existiert nicht → ungültig")
        return True

    try:
        # Verwende mtime (Zeitpunkt der letzten Inhaltsänderung) statt ctime,
        # denn ctime kann sich auch durch Metadaten-Änderungen verschieben.
        modification_time = datetime.datetime.fromtimestamp(path.stat().st_mtime)
    except OSError as e:
        module.debug(
            msg=f"Fehler beim Lesen der Modifikationszeit von '{cache_file_name}': {e} → Cache ungültig"
        )
        return True

    now = datetime.datetime.now()
    diff_minutes = (now - modification_time).total_seconds() / 60
    is_expired = diff_minutes > cache_minutes

    module.debug(
        msg=f"Cache-Datei '{cache_file_name}' gefunden. Letzte Änderung: {modification_time.isoformat()}"
    )
    module.debug(msg=f"  → Jetzt:       {now.isoformat()}")
    module.debug(
        msg=f"  → Alter:       {diff_minutes:.2f} Minuten (Limit: {cache_minutes} Minuten)"
    )
    module.debug(msg=f"  → Abgelaufen:  {is_expired}")

    # Wenn abgelaufen und löschen erwünscht, versuche die Datei zu entfernen
    if is_expired and cache_file_remove:
        try:
            path.unlink()
            module.debug(
                msg=f"  → Alte Cache-Datei '{cache_file_name}' wurde gelöscht."
            )
        except OSError as e:
            module.debug(
                msg=f"  → Fehler beim Löschen der Cache-Datei '{cache_file_name}': {e}"
            )

    return is_expired
