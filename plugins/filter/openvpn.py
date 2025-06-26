# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'openvpn_clients': self.openvpn_clients,
        }

    def openvpn_clients(self, data, hostvars):
        """
                combined_list: "{{ combined_list | default([]) + hostvars[item].openvpn_mobile_clients }}"
        """
        # display.v(f"openvpn_clients({data}, {hostvars})")
        client = hostvars.get("openvpn_mobile_clients", None)
        if client and isinstance(client, list):
            data += client

        return data
