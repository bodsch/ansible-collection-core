# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
from ansible.utils.display import Display

import re
import os

__metaclass__ = type

display = Display()


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'get_service': self.get_service,
            'log_directories': self.log_directories,
            'syslog_network_definition': self.syslog_network_definition,
        }

    def get_service(self, data, search_for):
        """
        """
        name = None
        regex_list_compiled = re.compile(f"^{search_for}.*")

        match = {k: v for k, v in data.items() if re.match(regex_list_compiled, k)}

        # display.vv(f"found: {match}  {type(match)} {len(match)}")

        if isinstance(match, dict) and len(match) > 0:
            values = list(match.values())[0]
            name = values.get('name', search_for).replace('.service', '')

        # display.vv(f"= result {name}")
        return name

    def log_directories(self, data, base_directory):
        """
          return a list of directories
        """
        # display.v(f"log_directories(self, {data}, {base_directory})")
        log_dirs = []
        log_files = sorted([v.get('file_name') for k, v in data.items() if v.get('file_name')])
        unique = list(dict.fromkeys(log_files))
        for d in unique:
            if "/$" in d:
                clean_dir_name = d.split("/$")[0]
                log_dirs.append(clean_dir_name)

        unique_dirs = list(dict.fromkeys(log_dirs))

        log_dirs = []

        for file_name in unique_dirs:
            full_file_name = os.path.join(
                base_directory,
                file_name
            )
            log_dirs.append(full_file_name)

        # display.v(f"= result {log_dirs}")
        return log_dirs

    def validate_syslog_destination(self, data):
        """
        """
        pass

    def syslog_network_definition(self, data, conf_type="source"):
        """
        """
        # display.v(f"syslog_network_definition({data}, {conf_type})")

        def as_boolean(value):
            return 'yes' if value else 'no'

        def as_string(value):
            return f"\"{value}\""

        def as_list(value):
            return ", ".join(value)

        res = {}
        if isinstance(data, dict):

            for key, value in data.items():
                if key == "ip":
                    if conf_type == "source":
                        res = dict(
                            ip=f"({value})"
                        )
                    else:
                        res = dict(
                            ip=f"\"{value}\""
                        )
                else:
                    if isinstance(value, bool):
                        value = f"({as_boolean(value)})"
                    elif isinstance(value, str):
                        value = f"({as_string(value)})"
                    elif isinstance(value, int):
                        value = f"({value})"
                    elif isinstance(value, list):
                        value = f"({as_list(value)})"
                    elif isinstance(value, dict):
                        value = self.syslog_network_definition(value, conf_type)

                    res.update({
                        key: value
                    })

        if isinstance(data, str):
            res = data

        # display.v(f"= res {res}")
        return res
