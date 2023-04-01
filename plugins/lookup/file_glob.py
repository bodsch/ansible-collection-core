# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# "MODIFED WITH https://github.com/philfry/ansible/blob/37c616dc76d9ebc3cbf0285a22e55f0e4db4185e/lib/ansible/plugins/lookup/fileglob.py"

from __future__ import (absolute_import, division, print_function)
from ansible.module_utils._text import to_bytes, to_text
from ansible.utils.display import Display
from ansible.plugins.lookup import LookupBase
import glob
import os

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

    def run(self, terms, variables=None, **kwargs):

        self.set_options(direct=kwargs)

        paths = []
        ansible_search_path = variables.get('ansible_search_path', None)
        role_path = variables.get('role_path')
        lookup_search_path = variables.get('search_path', None)

        if ansible_search_path:
            paths = ansible_search_path
        else:
            paths.append(self.get_basedir(variables))

        if lookup_search_path:
            if isinstance(lookup_search_path, list):
                for p in lookup_search_path:
                    paths.append(os.path.join(role_path, p))

        search_path = ['templates', 'files']

        ret = []
        found_templates = []

        for term in terms:
            """
            """
            for p in paths:
                for sp in search_path:
                    path = os.path.join(p, sp)
                    display.vv(f" - lookup in directory: {path}")
                    r = self._find_recursive(folder=path, extension=term)
                    if len(r) > 0:
                        found_templates.append(r)

        ret = self._flatten(found_templates)

        display.vv(f"found_templates {ret}")

        return ret

    def _find_recursive(self, folder, extension):
        """
        """
        matches = []

        for root, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                if filename.endswith(extension):
                    matches.append(os.path.join(root, filename))

        return matches
