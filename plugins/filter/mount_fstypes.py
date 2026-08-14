# python 3 headers, required if submitting to Ansible

from __future__ import annotations

from ansible.utils.display import Display

display = Display()


class FilterModule:
    """
    Ansible file jinja2 tests
    """

    def filters(self):
        return {"fstypes": self.fstypes}

    def fstypes(self, data):
        """ """
        result = []

        display.vv(f"bodsch.core.fstypes({data}")

        result = [d["fstype"] for d in data]

        display.v(f"result {result} {type(result)}")

        return result
