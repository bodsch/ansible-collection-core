#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
# (c) 2017 Ansible Project
# (c) 2022-2023, Bodo Schulz <bodo@boone-schulz.de>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# "MODIFED WITH https://github.com/philfry/ansible/blob/37c616dc76d9ebc3cbf0285a22e55f0e4db4185e/lib/ansible/plugins/lookup/fileglob.py"

from __future__ import absolute_import, division, print_function

import os
import re
from typing import Any, Dict, List, Optional

# from ansible.utils.listify import listify_lookup_plugin_terms as listify
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

__metaclass__ = type

DOCUMENTATION = """
    name: fileglob
    author: Bodo Schulz
    version_added: "1.0.4"
    short_description: list files matching a pattern
    description:
        - Find all files in a directory tree that match a pattern (recursively).
    options:
      _terms:
        required: False
        description: File extension on which a comparison is to take place.
        type: str
      search_path:
        required: False
        description: A list of additional directories to be searched.
        type: list
        default: []
        version_added: "1.0.4"
    notes:
      - Patterns are only supported on files, not directory/paths.
      - Matching is against local system files on the Ansible controller.
        To iterate a list of files on a remote node, use the M(ansible.builtin.find) module.
      - Returns a string list of paths joined by commas, or an empty list if no files match. For a 'true list' pass C(wantlist=True) to the lookup.
"""

EXAMPLES = """
- name: Display paths of all .tpl files
  ansible.builtin.debug:
    msg: "{{ lookup('bodsch.core.file_glob', '.tpl') }}"

- name: Show paths of all .tpl files, extended by further directories
  ansible.builtin.debug:
    msg: "{{ lookup('bodsch.core.file_glob', '.tpl') }}"
  vars:
    search_path:
      - ".."
      - "../.."

- name: Copy each file over that matches the given pattern
  ansible.builtin.copy:
    src: "{{ item }}"
    dest: "/etc/fooapp/"
    owner: "root"
    mode: 0600
  with_file_glob:
    - "*.tmpl"

- name: Copy each template over that matches the given pattern
  ansible.builtin.copy:
    src: "{{ item }}"
    dest: "/etc/alertmanager/templates/"
    owner: "root"
    mode: 0640
  with_file_glob:
    - ".tmpl"
  vars:
    search_path:
      - ".."
      - "../.."
"""

RETURN = """
  _list:
    description:
      - list of files
    type: list
    elements: path
"""

display = Display()


class LookupModule(LookupBase):
    """
    Ansible lookup plugin that finds files matching an extension in role
    or playbook search paths.

    The plugin:
      * Resolves search locations based on Ansible's search paths and optional
        user-specified paths.
      * Recursively walks the "templates" and "files" directories.
      * Returns a flat list of matching file paths.
    """

    def __init__(self, basedir: Optional[str] = None, **kwargs: Any) -> None:
        """
        Initialize the lookup module.

        The base directory is stored for potential use by Ansible's lookup base
        mechanisms.

        Args:
            basedir: Optional base directory for lookups, usually supplied by Ansible.
            **kwargs: Additional keyword arguments passed from Ansible.

        Returns:
            None
        """
        self.basedir = basedir

    def run(
        self,
        terms: List[str],
        variables: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """
        Execute the fileglob lookup.

        For each term (interpreted as a file extension), this method searches
        recursively under all derived search paths and returns a flattened list
        of matching file paths.

        Args:
            terms: A list of file extensions or patterns (e.g. ['.tpl']).
            variables: The Ansible variable context, used to determine
                - ansible_search_path
                - role_path
                - search_path (custom additional paths)
                - search_regex (optional filename regex filter)
            **kwargs: Additional lookup options, passed through to set_options().

        Returns:
            list[str]: A list containing the full paths of all files matching
            the provided extensions within the resolved search directories.
        """
        display.vv(f"run({terms}, variables, {kwargs})")
        self.set_options(direct=kwargs)

        paths: List[str] = []
        ansible_search_path = variables.get("ansible_search_path", None)
        role_path = variables.get("role_path")
        lookup_search_path = variables.get("search_path", None)
        lookup_search_regex = variables.get("search_regex", None)

        if ansible_search_path:
            paths = ansible_search_path
        else:
            paths.append(self.get_basedir(variables))

        if lookup_search_path:
            if isinstance(lookup_search_path, list):
                for p in lookup_search_path:
                    paths.append(os.path.join(role_path, p))

        search_path = ["templates", "files"]

        ret: List[str] = []
        found_files: List[List[str]] = []

        for term in terms:
            """ """
            for p in paths:
                for sp in search_path:
                    path = os.path.join(p, sp)
                    display.vv(f" - lookup in directory: {path}")
                    r = self._find_recursive(
                        folder=path, extension=term, search_regex=lookup_search_regex
                    )
                    # display.vv(f"   found: {r}")
                    if len(r) > 0:
                        found_files.append(r)

        ret = self._flatten(found_files)

        return ret

    def _find_recursive(
        self,
        folder: str,
        extension: str,
        search_regex: Optional[str] = None,
    ) -> List[str]:
        """
        Recursively search for files in the given folder that match an extension
        and an optional regular expression.

        Args:
            folder: The root directory to walk recursively.
            extension: The file extension to match (e.g. ".tpl").
            search_regex: Optional regular expression string. If provided, only
                filenames matching this regex are included.

        Returns:
            list[str]: A list containing the full paths of matching files found
            under the given folder. If no files match, an empty list is returned.
        """
        # display.vv(f"_find_recursive({folder}, {extension}, {search_regex})")
        matches: List[str] = []

        for root, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                if filename.endswith(extension):
                    if search_regex:
                        reg = re.compile(search_regex)
                        if reg.match(filename):
                            matches.append(os.path.join(root, filename))
                    else:
                        matches.append(os.path.join(root, filename))

        return matches
