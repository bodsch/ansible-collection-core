# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
from ansible.utils.display import Display

import re
# import os
import json

__metaclass__ = type

display = Display()


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'merge_lists': self.merge_lists,
        }



    def merge_lists(self, defaults, data):
        """
        """
        count_defaults = len(defaults)
        count_data = len(data)

        display.v("defaults: ({type}) {len} - {data} entries".format(data=defaults, type=type(defaults), len=count_defaults))
        display.vv(json.dumps(data, indent=2, sort_keys=False))
        display.v("data    : ({type}) {len} - {data} entries".format(data=data, type=type(data), len=count_data))

        result = []

        # short way
        if count_defaults == 0:
            return data # self.__sort_list(data, 'host')

        if count_data == 0:
            return defaults # self.__sort_list(defaults, 'host')

        # our new list from users input
        for d in data:
            _name = d['host']
            # search the name in the default map
            _defaults_name = self.__search(defaults, _name)

            display.v(f"  _defaults_name    : {_defaults_name}")
            # when not found, put these on the new result list
            if not _defaults_name:
                result.append(_defaults_name)
            else:
                # when found, remove these entry from the defaults list, its obsolete
                for i in range(len(defaults)):
                    if defaults[i]['host'] == _name:
                        del defaults[i]
                        break

        # add both lists and sort
        result = data + defaults # self.__sort_list(data + defaults, 'host')

        display.v(f"= result: {result}")

        return result

    def __sort_list(self, _list, _filter):
        return sorted(_list, key=lambda k: k.get(_filter))

    def __search(self, d, name):
        res = None
        for sub in d:
            if sub['host'] == name:
                res = sub
                break

        return res
