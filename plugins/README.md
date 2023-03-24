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

## module_utils

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
