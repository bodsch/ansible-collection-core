#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory
from ansible_collections.bodsch.core.plugins.module_utils.file import (chmod, remove_file)
from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum

import os
import json

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: facts
version_added: 1.0.10
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Write Ansible Facts

description:
    - Write Ansible Facts

options:
  state:
    description:
      - Whether to create (C(present)), or remove (C(absent)) a fact.
    required: false
  name:
    description:
      - The name of the fact.
    type: str
    required: true
  facts:
    description:
      - A dictionary with information to be written in the facts.
    type: dict
    required: true
"""

EXAMPLES = """
- name: create custom facts
  bodsch.core.facts:
    state: present
    name: icinga2
    facts:
      version: "2.10"
      salt: fgmklsdfnjyxnvjksdfbkuser
      user: icinga2
"""

RETURN = """
msg:
  description: Module information
  type: str
"""

# ---------------------------------------------------------------------------------------

TPL_FACT = """#!/usr/bin/env bash
# generated by ansible
cat <<EOF
{{ item | tojson(indent=2) }}
EOF

"""


class AnsibleFacts(object):
    """
      Main Class
    """
    module = None

    def __init__(self, module):
        """
          Initialize all needed Variables
        """
        self.module = module

        self.verbose = module.params.get("verbose")
        self.state = module.params.get("state")
        self.name = module.params.get("name")
        self.facts = module.params.get("facts")
        self.append = module.params.get("append")

        self.cache_directory = f"/var/cache/ansible/{self.name}"
        self.checksum_file = os.path.join(self.cache_directory, "facts.checksum")
        self.json_file = os.path.join(self.cache_directory, "facts.json")
        self.facts_directory = "/etc/ansible/facts.d"
        self.facts_file = os.path.join(self.facts_directory, f"{self.name}.fact")

    def run(self):
        """
          runner
        """
        create_directory(self.cache_directory)
        create_directory(self.facts_directory, mode="0775")

        old_facts = {}

        _failed = False
        _changed = False
        _msg = "There are no changes."

        checksum = None

        if self.state == "absent":
            for f in [self.checksum_file, self.json_file, self.facts_file]:
                if os.path.exists(f):
                    remove_file(f)
                    _changed = True
                    _msg = "The facts have been successfully removed."

            return dict(
                changed=_changed,
                msg=_msg
            )

        checksum = Checksum(self.module)

        if not os.path.exists(self.facts_file):
            if os.path.exists(self.checksum_file):
                os.remove(self.checksum_file)
            if os.path.exists(self.json_file):
                os.remove(self.json_file)

        if os.path.exists(self.json_file):
            with open(self.json_file) as f:
                old_facts = json.load(f)

        # self.module.log(f" old_facts  : {old_facts}")

        old_checksum = checksum.checksum(old_facts)
        new_checksum = checksum.checksum(self.facts)

        changed = not (old_checksum == new_checksum)

        # self.module.log(f" changed       : {changed}")
        # self.module.log(f" new_checksum  : {new_checksum}")
        # self.module.log(f" old_checksum  : {old_checksum}")

        if self.append and changed:
            self.facts.update(old_facts)
            changed= True

        # self.module.log(f" facts       : {self.facts}")

        if not changed:
            return dict(
                changed=False,
            )

        # Serializing json
        json_object = json.dumps(self.facts, indent=2)

        # Writing to sample.json
        with open(self.facts_file, "w") as outfile:
            outfile.write("#!/usr/bin/env bash\n# generated by ansible\ncat <<EOF\n")

        with open(self.facts_file, "a+") as outfile:
            outfile.write(json_object + "\nEOF\n")

        with open(self.json_file, "w") as outfile:
            outfile.write(json.dumps(self.facts))

        # write_template(self.facts_file, TPL_FACT, self.facts)
        chmod(self.facts_file, "0775")

        checksum.write_checksum(self.checksum_file, new_checksum)

        return dict(
            failed=_failed,
            changed=True,
            msg="The facts have been successfully written."
        )

    def __has_changed(self, data_file, checksum_file, data):
        """
        """
        old_checksum = ""

        if not os.path.exists(data_file) and os.path.exists(checksum_file):
            """
            """
            os.remove(checksum_file)

        if os.path.exists(checksum_file):
            with open(checksum_file, "r") as f:
                old_checksum = f.readlines()[0]

        if isinstance(data, str):
            _data = sorted(data.split())
            _data = '\n'.join(_data)

        checksum = self.__checksum(_data)
        changed = not (old_checksum == checksum)

        if self.force:
            changed = True
            old_checksum = ""

        # self.module.log(msg=f" - new  checksum '{checksum}'")
        # self.module.log(msg=f" - curr checksum '{old_checksum}'")
        # self.module.log(msg=f" - changed       '{changed}'")

        return changed, checksum, old_checksum


def main():

    args = dict(
        state=dict(
            choices=[
                "present",
                "absent",
            ],
            default="present"
        ),
        name=dict(
            type="str",
            required=True,
        ),
        facts=dict(
            type="dict",
            required=True,
        ),
        append=dict(
            type="bool",
            required=False,
            default=True
        )
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    obj = AnsibleFacts(module)
    result = obj.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
