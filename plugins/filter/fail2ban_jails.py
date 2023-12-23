# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
        Ansible file jinja2 tests
    """

    def filters(self):
        return {
            'merge_jails': self.merge_jails,
        }

    def __merge_two_dicts(self, x, y):
        z = x.copy()   # start with x's keys and values
        z.update(y)    # modifies z with y's keys and values & returns None
        return z

    def __search(self, d, name):
        res = None
        for sub in d:
            if sub['name'] == name:
                res = sub
                break

        return res

    def __sort_list(self, _list, _filter):
        return sorted(_list, key=lambda k: k.get(_filter))

    def merge_jails(self, defaults, data):
        """
        """
        count_defaults = len(defaults)
        count_data = len(data)

        # display.v("defaults: ({type}) {len} - {data} entries".format(data=defaults, type=type(defaults), len=count_defaults))
        # display.vv(json.dumps(data, indent=2, sort_keys=False))
        # display.v("data    : ({type}) {len} - {data} entries".format(data=data, type=type(data), len=count_data))

        result = []

        # short way
        if count_defaults == 0:
            return self.__sort_list(data, 'name')

        if count_data == 0:
            return self.__sort_list(defaults, 'name')

        # our new list from users input
        for d in data:
            _name = d['name']
            # search the name in the default map
            _defaults_name = self.__search(defaults, _name)
            # when not found, put these on the new result list
            if not _defaults_name:
                result.append(_defaults_name)
            else:
                # when found, remove these entry from the defaults list, its obsolete
                for i in range(len(defaults)):
                    if defaults[i]['name'] == _name:
                        del defaults[i]
                        break

        # add both lists and sort
        result = self.__sort_list(data + defaults, 'name')

        return result
