# Collections Plugins Directory

## modules

### remove_ansible_backups

```shell
ansible-doc --type module bodsch.core.remove_ansible_backups
> BODSCH.CORE.REMOVE_ANSIBLE_BACKUPS    (./collections/ansible_collections/bodsch/core/plugins/modules/remove_ansible_backups.py)

        Remove older backup files created by ansible
```

### package_version

```shell
ansible-doc --type module bodsch.core.package_version
> BODSCH.CORE.PACKAGE_VERSION    (./collections/ansible_collections/bodsch/core/plugins/modules/package_version.py)

        Attempts to determine the version of a package to be installed or already installed. Supports apt, pacman, dnf (or yum) as
        package manager.
```

### aur

```shell
ansible-doc --type module bodsch.core.aur
> BODSCH.CORE.AUR    (./collections/ansible_collections/bodsch/core/plugins/modules/aur.py)

        This modules manages packages for ArchLinux on a target with aur (like [ansible.builtin.yum], [ansible.builtin.apt], ...).
```

### journalctl

```shell
> BODSCH.CORE.JOURNALCTL    (./collections/ansible_collections/bodsch/core/plugins/modules/journalctl.py)

        Query the systemd journal with a very limited number of possible parameters. In certain cases there are errors that are not
        clearly traceable but are logged in the journal. This module is intended to be a tool for error analysis.
```

### facts

```shell

> BODSCH.CORE.FACTS    (./collections/ansible_collections/bodsch/core/plugins/modules/facts.py)

        Write Ansible Facts
```

## module_utils

### `checksum`

```python
from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum

c = Checksum()

print(c.checksum("fooo"))
print(c.checksum_from_file("/etc/fstab"))

# ???
c.compare("aaa", "bbb")
c.save("test-check", "aaa")
c.load("test-check")
```

### `file`

```python
from ansible_collections.bodsch.core.plugins.module_utils.file import remove_file, create_link
```

- `create_link(source, destination, force=False)`
- `remove_file(file_name)`

### `directory`

```python
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory
```

- `create_directory(directory)`
- `permstr_to_octal(modestr, umask)`
- `current_state(directory)`
- `fix_ownership(directory, force_owner=None, force_group=None, force_mode=False)`


### `cache`

```python
from ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid import cache_valid
```

- `cache_valid(module, cache_file_name, cache_minutes=60, cache_file_remove=True)`

### `template`

## lookup

### `file_glob`

## filter

### `types`

- `type()`
- `config_bool(data, true_as="yes", false_as="no")`

### `verify`

- `compare_list(data_list, compare_to_list)`
- `upgrade(install_path, bin_path)`

### `dns`

- `dns_lookup(timeout=3, extern_resolver=[])`

### `python`

- `python_extra_args(python_version=ansible_python.version, extra_args=[], break_system_packages=True)`

### `union_by`

- `union(docker_defaults_python_packages, union_by='name')`

### - `parse_checksum`

- `parse_checksum('nginx-prometheus-exporter', ansible_facts.system, system_architecture)`

## misc

This directory can be used to ship various plugins inside an Ansible collection. Each plugin is placed in a folder that
is named after the type of plugin it is in. It can also include the `module_utils` and `modules` directory that
would contain module utils and modules respectively.

Here is an example directory of the majority of plugins currently supported by Ansible:

```
└── plugins
    ├── action
    ├── become
    ├── cache
    ├── callback
    ├── cliconf
    ├── connection
    ├── filter
    ├── httpapi
    ├── inventory
    ├── lookup
    ├── module_utils
    ├── modules
    ├── netconf
    ├── shell
    ├── strategy
    ├── terminal
    ├── test
    └── vars
```

A full list of plugin types can be found at [Working With Plugins](https://docs.ansible.com/ansible-core/2.14/plugins/plugins.html).
