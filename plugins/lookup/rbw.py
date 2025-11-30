from __future__ import absolute_import, division, print_function

"""
Ansible lookup plugin to read secrets from Vaultwarden using the rbw CLI.

This module provides the `LookupModule` class, which integrates the `rbw`
command line client into Ansible as a lookup plugin. It supports optional
index-based lookups, JSON parsing of secrets, and on-disk caching for both
the rbw index and retrieved secrets.
"""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

display = Display()

DOCUMENTATION = """
lookup: rbw
author:
  - Bodo 'bodsch' (@bodsch)
version_added: "1.0.0"
short_description: Read secrets from Vaultwarden via the rbw CLI
description:
  - This lookup plugin retrieves entries from Vaultwarden using the 'rbw' CLI client.
  - It supports selecting specific fields, optional JSON parsing, and structured error handling.
  - Supports index-based lookups for disambiguation by name/folder/user.
options:
  _terms:
    description:
      - The Vault entry to retrieve, specified by path, name, or UUID.
    required: true
  field:
    description:
      - Optional field within the entry to return (e.g., username, password).
    required: false
    type: str
  parse_json:
    description:
      - If set to true, the returned value will be parsed as JSON.
    required: false
    type: bool
    default: false
  strict_json:
    description:
      - If true and parse_json is enabled, invalid JSON will raise an error.
      - If false, invalid JSON will return an empty dictionary.
    required: false
    type: bool
    default: false
  use_index:
    description:
      - If true, the index will be used to map name/folder/user to a unique id.
    required: false
    type: bool
    default: false
"""

EXAMPLES = """
- name: Read a password from Vault by UUID
  debug:
    msg: "{{ lookup('bodsch.core.rbw', '0123-uuid-4567', field='password') }}"

- name: Read a password using index
  debug:
    msg: "{{ lookup('bodsch.core.rbw',
      {'name': 'expresszuschnitt.de', 'folder': '.immowelt.de', 'user': 'immo@boone-schulz.de'},
      field='password',
      use_index=True) }}"

- name: Multi-fetch
  set_fact:
    multi: "{{ lookup('bodsch.core.rbw',
      [{'name': 'foo', 'folder': '', 'user': ''}, 'some-uuid'],
      field='username',
      use_index=True) }}"
"""

RETURN = """
_raw:
  description:
    - The raw value from the Vault entry, either as a string or dictionary (if parse_json is true).
  type: raw
"""


class LookupModule(LookupBase):
    """
    Ansible lookup module for retrieving secrets from Vaultwarden via the rbw CLI.

    The plugin supports:
      * Lookup by UUID or by a combination of name, folder, and user.
      * Optional index-based resolution to derive a stable entry ID.
      * On-disk caching of both the rbw index and individual lookups.
      * Optional JSON parsing of retrieved secret values.

    Attributes:
        CACHE_TTL (int): Time-to-live for cache entries in seconds.
        cache_directory (str): Base directory path for index and value caches.
    """

    CACHE_TTL = 300  # 5 Minuten
    cache_directory = f"{Path.home()}/.cache/ansible/lookup/rbw"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the lookup module and ensure the cache directory exists.

        Args:
            *args: Positional arguments passed through to the parent class.
            **kwargs: Keyword arguments passed through to the parent class.

        Returns:
            None
        """
        super(LookupModule, self).__init__(*args, **kwargs)
        if not os.path.exists(self.cache_directory):
            os.makedirs(self.cache_directory, exist_ok=True)

    def run(self, terms, variables=None, **kwargs) -> List[Any]:
        """
        Execute the lookup and return the requested values.

        This method is called by Ansible when the lookup plugin is used. It
        resolves each term into an rbw entry ID (optionally using the index),
        retrieves and caches the value, and optionally parses the value as JSON.

        Args:
            terms: A list of lookup terms. Each term can be either:
                * A string representing an entry ID or name.
                * A dict with keys "name", "folder", and "user" for index-based lookup.
            variables: Ansible variables (unused, but part of the standard interface).
            **kwargs: Additional keyword arguments:
                * field (str): Optional field within the entry to return.
                * parse_json (bool): Whether to parse the result as JSON.
                * strict_json (bool): If True, invalid JSON raises an error.
                * use_index (bool): If True, resolve name/folder/user via rbw index.

        Returns:
            list: A list of values corresponding to the supplied terms. Each element
            is either:
                * A string (raw secret) when parse_json is False.
                * A dict (parsed JSON) when parse_json is True.

        Raises:
            AnsibleError: If input terms are invalid, the index lookup fails,
                the rbw command fails, or JSON parsing fails in strict mode.
        """
        display.v(f"run(terms={terms}, kwargs={kwargs})")

        if not terms or not isinstance(terms, list) or not terms[0]:
            raise AnsibleError("At least one Vault entry must be specified.")

        field = kwargs.get("field", "").strip()
        parse_json = kwargs.get("parse_json", False)
        strict_json = kwargs.get("strict_json", False)
        use_index = kwargs.get("use_index", False)

        index_data: Optional[Dict[str, Any]] = None
        if use_index:
            index_data = self._read_index()
            if index_data is None:
                index_data = self._fetch_index()
            display.v(f"Index has {len(index_data['entries'])} entries")

        results: List[Any] = []

        for term in terms:
            if isinstance(term, dict):
                name = term.get("name", "").strip()
                folder = term.get("folder", "").strip()
                user = term.get("user", "").strip()
                raw_entry = f"{name}|{folder}|{user}"
            else:
                name = term.strip()
                folder = ""
                user = ""
                raw_entry = name

            if not name:
                continue

            entry_id = name  # fallback: use directly

            if index_data:
                matches = [
                    e
                    for e in index_data["entries"]
                    if e["name"] == name
                    and (not folder or e["folder"] == folder)
                    and (not user or e["user"] == user)
                ]

                if not matches:
                    raise AnsibleError(
                        f"No matching entry found in index for: {raw_entry}"
                    )

                if len(matches) > 1:
                    raise AnsibleError(
                        f"Multiple matches found in index for: {raw_entry}"
                    )

                entry_id = matches[0]["id"]
                display.v(f"Resolved {raw_entry} → id={entry_id}")

            cache_key = self._cache_key(entry_id, field)
            cached = self._read_cache(cache_key)

            if cached is not None:
                value = cached
                display.v(f"Cache HIT for {entry_id}")
            else:
                value = self._fetch_rbw(entry_id, field)
                self._write_cache(cache_key, value)
                display.v(f"Cache MISS for {entry_id} — fetched with rbw")

            if parse_json:
                try:
                    results.append(json.loads(value))
                except json.decoder.JSONDecodeError as e:
                    if strict_json:
                        raise AnsibleError(
                            f"JSON parsing failed for entry '{entry_id}': {e}"
                        )
                    else:
                        display.v(
                            f"Warning: Content of '{entry_id}' is not valid JSON."
                        )
                        results.append({})
                except Exception as e:
                    raise AnsibleError(f"Unexpected error parsing '{entry_id}': {e}")
            else:
                results.append(value)

        return results

    def _fetch_rbw(self, entry_id: str, field: str) -> str:
        """
        Call the rbw CLI to retrieve a specific entry or entry field.

        Args:
            entry_id: The rbw entry identifier (UUID or resolved ID from index).
            field: Optional field name to retrieve (e.g. "username", "password").
                If empty, the default value for the entry is returned.

        Returns:
            str: The trimmed stdout of the rbw command, representing the secret value.

        Raises:
            AnsibleError: If the rbw command exits with a non-zero status.
        """
        cmd = ["rbw", "get"]
        if field:
            cmd.extend(["--field", field])
        cmd.append(entry_id)

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() or e.stdout.strip()
            raise AnsibleError(f"Error retrieving Vault entry '{entry_id}': {err_msg}")

    def _fetch_index(self) -> Dict[str, Any]:
        """
        Fetch the rbw index and persist it in the local cache.

        The index contains a list of entries, each with id, user, name, and folder.
        It is stored on disk together with a timestamp and used for subsequent
        lookups until it expires.

        Returns:
            dict: A dictionary with:
                * "timestamp" (float): Unix timestamp when the index was fetched.
                * "entries" (list[dict]): List of index entries.

        Raises:
            AnsibleError: If the rbw index command fails.
        """
        cmd = ["rbw", "list", "--fields", "id,user,name,folder"]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            lines = [
                line.strip() for line in result.stdout.splitlines() if line.strip()
            ]

            headers = ["id", "user", "name", "folder"]

            entries: List[Dict[str, str]] = []
            for line in lines:
                parts = line.split("\t")
                if len(parts) < len(headers):
                    parts += [""] * (len(headers) - len(parts))
                entry = dict(zip(headers, parts))
                entries.append(entry)

            index_payload: Dict[str, Any] = {
                "timestamp": time.time(),
                "entries": entries,
            }

            self._write_index(index_payload)
            return index_payload

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() or e.stdout.strip()
            raise AnsibleError(f"Error retrieving rbw index: {err_msg}")

    def _index_path(self) -> str:
        """
        Compute the absolute file path of the index cache.

        Returns:
            str: The full path to the index cache file.
        """
        return os.path.join(self.cache_directory, "index.json")

    def _read_index(self) -> Optional[Dict[str, Any]]:
        """
        Read the rbw index from the cache if it exists and is still valid.

        The index is considered valid if its age is less than or equal to
        CACHE_TTL. If the index is expired or cannot be read, it is removed.

        Returns:
            dict | None: The cached index payload if available and not expired,
            otherwise None.

        """
        path = self._index_path()
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            age = time.time() - payload["timestamp"]
            if age <= self.CACHE_TTL:
                return payload
            else:
                os.remove(path)
                return None
        except Exception as e:
            display.v(f"Index cache read error: {e}")
            return None

    def _write_index(self, index_payload: Dict[str, Any]) -> None:
        """
        Persist the rbw index payload to disk.

        Args:
            index_payload: The payload containing the index data and timestamp.

        Returns:
            None
        """
        path = self._index_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(index_payload, f)
        except Exception as e:
            display.v(f"Index cache write error: {e}")

    def _cache_key(self, entry_id: str, field: str) -> str:
        """
        Create a deterministic cache key for a given entry and field.

        Args:
            entry_id: The rbw entry identifier.
            field: The requested field name. May be an empty string.

        Returns:
            str: A SHA-256 hash hex digest representing the cache key.
        """
        raw_key = f"{entry_id}|{field}".encode("utf-8")
        return hashlib.sha256(raw_key).hexdigest()

    def _cache_path(self, key: str) -> str:
        """
        Compute the absolute file path for a given cache key.

        Args:
            key: The cache key as returned by `_cache_key`.

        Returns:
            str: The full path to the cache file for the given key.
        """
        return os.path.join(self.cache_directory, key + ".json")

    def _read_cache(self, key: str) -> Optional[str]:
        """
        Read a cached value for the given key if present and not expired.

        The cache entry is considered valid if its age is less than or equal to
        CACHE_TTL. If the entry is expired or cannot be read, it is removed.

        Args:
            key: The cache key as returned by `_cache_key`.

        Returns:
            str | None: The cached value if present and not expired,
            otherwise None.
        """
        path = self._cache_path(key)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            age = time.time() - payload["timestamp"]
            if age <= self.CACHE_TTL:
                return payload["value"]
            else:
                os.remove(path)
                return None
        except Exception as e:
            display.v(f"Cache read error for key {key}: {e}")
            return None

    def _write_cache(self, key: str, value: str) -> None:
        """
        Write a value to the cache using the given key.

        Args:
            key: The cache key as returned by `_cache_key`.
            value: The value to be cached, typically the raw secret string.

        Returns:
            None
        """
        path = self._cache_path(key)
        payload = {
            "timestamp": time.time(),
            "value": value,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception as e:
            display.v(f"Cache write error for key {key}: {e}")
