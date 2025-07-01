

from __future__ import (absolute_import, division, print_function)
import subprocess
import json
import json.decoder

from ansible.utils.display import Display
# from ansible.utils.listify import listify_lookup_plugin_terms as listify
from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError

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
"""

EXAMPLES = """
- name: Read a password from Vault
  ansible.builtin.debug:
    msg: "{{ lookup('bodsch.core.rbw', 'prod/webapp/db', field='password') }}"

- name: Read a password from Vault
  ansible.builtin.debug:
    msg: "{{ lookup('bodsch.core.rbw', 'd806a796436a-4d7d-5a23-96a2-5bc6ed75', field='url') }}"

- name: Read a Vault entry and parse it as JSON
  ansible.builtin.set_fact:
    credentials: "{{ lookup('bodsch.core.rbw', 'prod/webapp/credentials', parse_json=True) }}"

- name: Fail on invalid JSON data
  ansible.builtin.set_fact:
    config: "{{ lookup('bodsch.core.rbw', 'prod/webapp/settings', parse_json=True, strict_json=True) }}"
"""

RETURN = """
_raw:
  description:
    - The raw value from the Vault entry, either as a string or dictionary (if parse_json is true).
  type: raw
"""

# ------------------------------------------------------------------------------------------------


def format_error(entry_id, context, error):
    """
    entry_id: z.B. uuid oder slug
    context: Klartext wie 'JSON-Parsing', 'Vault-Zugriff'
    error: Exception oder str
    """
    if isinstance(error, Exception):
        msg = str(error).strip()
    else:
        msg = error
    return f"[{context}] for '{entry_id}': {msg}"


class LookupModule(LookupBase):
    """
    """

    def run(self, terms, variables=None, **kwargs):
        """
        """
        display.v(f"run(terms={terms}, variables, kwargs={kwargs})")

        if not terms or not terms[0]:
            display.v("A structured Vault path is required (e.g. 'prod/webapp/db').")
            return [{}]
            # raise AnsibleError()

        entry = terms[0].strip()
        field = kwargs.get("field", "").strip()
        parse_json = kwargs.get("parse_json", False)
        strict_json = kwargs.get("strict_json", False)

        cmd = ["rbw", "get"]
        if field:
            cmd.extend(["--field", field])
        cmd.append(entry)

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            value = result.stdout.strip()

            display.v(f"{value}")

            if parse_json:
                try:
                    return json.loads(value)

                except json.decoder.JSONDecodeError as e:
                    if strict_json:
                        msg = f"JSON parsing failed for entry '{entry}'"
                        display.v(msg)
                        display.v(f"{e.msg} (Position {e.pos}")
                        raise AnsibleError(msg)
                    else:
                        # Optional: Logging für Debug-Modus
                        msg = f"Warning: Content of “{entry}” is not valid JSON."
                        display.v(msg)
                        return [{}]
                except Exception as e:
                    msg = f"Unexpected error parsing '{entry}'"
                    display.v(msg)
                    display.v(str(e))
                    raise AnsibleError(msg)

            else:
                return [value]

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() or e.stdout.strip()
            msg = f"Error retrieving Vault entry '{entry}'"
            raise AnsibleError(f"{msg}: {err_msg}")
