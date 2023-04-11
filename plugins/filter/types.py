# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
        Ansible file jinja2 tests
    """

    def filters(self):
        return {
            'type': self.var_type,
            'config_bool': self.config_bool_as_string,
        }

    def var_type(self, var):
        """
            Get the type of a variable
        """
        return type(var).__name__

    def config_bool_as_string(self, data, true_as="yes", false_as="no"):
        """
        """
        # display.v(f"config_bool({data}, {type(data)}, {true_as}, {false_as})")

        result = false_as

        if isinstance(data, bool):
            result = true_as if data else false_as

        if type(data) is None:
            result = False
        elif type(data) is bool:
            result = true_as if data else false_as
        else:
            result = data

        # display.v(f"return : {result}")
        return result
