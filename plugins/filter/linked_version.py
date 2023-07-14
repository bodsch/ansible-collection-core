# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, print_function)
__metaclass__ = type

from ansible.utils.display import Display
import os

display = Display()


class FilterModule(object):
    """
        Ansible file jinja2 tests
    """

    def filters(self):
        return {
            'linked_version': self.linked_version,
        }

    def linked_version(self, data, install_path, version):
        """
        """
        # display.v(f"linked_version(self, {data}, {install_path}, {version})")

        _exists = data.get("exists", False)

        if _exists:
            # _islink = data.get("islink", False)
            _lnk_source = data.get("lnk_source", None)
            _path = data.get("path", False)

            if _lnk_source:
                _path = os.path.dirname(_lnk_source)

            # display.v(f" - exists  : {_exists}")
            # display.v(f" - is link : {_islink}")
            # display.v(f" - link src: {_lnk_source}")
            # display.v(f" - path    : {_path}")

            state = (install_path == _path)

            # display.v(f" - state    : {state}")

            return state
        else:
            return True
