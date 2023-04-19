# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
      ansible filter
    """

    def filters(self):
        return {
            'compare_list': self.compare_list,
            'upgrade': self.upgrade,
        }

    def compare_list(self, data_list, compare_to_list):
        """
        """
        display.v(f"compare_list({data_list}, {compare_to_list})")

        result = []

        for i in data_list:
            if i in compare_to_list:
                result.append(i)

        display.v(f"return : {result}")
        return result

    def upgrade(self, install_path, bin_path):
        """
        """
        directory = None
        link_to_bin = None

        install_path_stats = install_path.get("stat", None)
        bin_path_stats = bin_path.get("stat", None)
        install_path_exists = install_path_stats.get("exists", False)
        bin_path_exists = bin_path_stats.get("exists", False)

        if install_path_exists:
            directory = install_path_stats.get("isdir", False)

        if bin_path_exists:
            link_to_bin = bin_path_stats.get("islnk", False)

        if bin_path_exists and not link_to_bin:
            result = True
        elif install_path_exists and directory:
            result = False
        else:
            result = False

        display.v(f"return : {result}")
        return result
