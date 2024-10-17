# Ansible Collection - bodsch.core

Documentation for the collection.

This collection aims to offer an set of small ansible modules or helper functions.


## Requirements & Dependencies

- `dnspython`
- `dirsync`

```bash
pip install dnspython
pip install dirsync
```


## Included content


## Roles

| Role                                                                       | Build State | Description |
|:---------------------------------------------------------------------------| :---- | :---- |
| [bodsch.core.pacman](./roles/pacman/README.md)                             | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/pacman.yml?branch=main)][pacman] | Ansible role to configure pacman. |
| [bodsch.core.fail2ban](./roles/fail2ban/README.md)                         | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/fail2ban.yml?branch=main)][fail2ban] | Installs and configure fail2ban |
| [bodsch.core.snakeoil](./roles/snakeoil/README.md)                         | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/snakeoil.yml?branch=main)][snakeoil] | build a simple snakeoil certificate for a test environment. |
| [bodsch.core.syslog_ng](./roles/syslog_ng/README.md)                       | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/syslog_ng.yml?branch=main)][syslog_ng] | Installs and configures a classic syslog-ng service for processing log files away from journald. |
| [bodsch.core.logrotate](./roles/logrotate/README.md)                       | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/logrotate.yml?branch=main)][logrotate] | Installs logrotate and provides an easy way to setup additional logrotate scripts |
| [bodsch.core.mount](./roles/mount/README.md)                               | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/mount.yml?branch=main)][mount] | Manage generic mountpoints |
| [bodsch.core.openvpn](./roles/openvpn/README.md)                           | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/openvpn.yml?branch=main)][openvpn] | Ansible role to install and configure openvpn server. |
| [bodsch.core.sysctl](./roles/sysctl/README.md)                             | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/sysctl.yml?branch=main)][sysctl] | Ansible role to configure sysctl. |

[pacman]: https://github.com/bodsch/ansible-collection-core/actions/workflows/pacman.yml
[fail2ban]: https://github.com/bodsch/ansible-collection-core/actions/workflows/fail2ban.yml
[snakeoil]: https://github.com/bodsch/ansible-collection-core/actions/workflows/snakeoil.yml
[syslog_ng]: https://github.com/bodsch/ansible-collection-core/actions/workflows/syslog_ng.yml
[logrotate]: https://github.com/bodsch/ansible-collection-core/actions/workflows/logrotate.yml
[mount]: https://github.com/bodsch/ansible-collection-core/actions/workflows/mount.yml
[openvpn]: https://github.com/bodsch/ansible-collection-core/actions/workflows/openvpn.yml
[sysctl]: https://github.com/bodsch/ansible-collection-core/actions/workflows/sysctl.yml

### Modules

| Name                      | Description |
|:--------------------------|:----|
| [remove_ansible_backups](./plugins/modules/remove_ansible_backups.py) | Remove older backup files created by ansible |
| [package_version](./plugins/modules/package_version.py)               | Attempts to determine the version of a package to be installed or already installed. |
| [aur](./plugins/modules/aur.py)                                       | Installing packages for ArchLinux with aur |
| [journalctl](./plugins/modules/journalctl.py)                         | Query the systemd journal with a very limited number of possible parameters |
| [facts](./plugins/modules/facts.py)                                   | Write ansible facts |
| [sync_directory](./plugins/modules/sync_directory.py)                 | Syncronises directories similar to rsync |



## Installing this collection

You can install the memsource collection with the Ansible Galaxy CLI:

```bash
#> ansible-galaxy collection install bodsch.core
```

To install directly from GitHub:

```bash
#> ansible-galaxy collection install git@github.com:bodsch/ansible-collection-core.git
```


You can also include it in a `requirements.yml` file and install it with `ansible-galaxy collection install -r requirements.yml`, using the format:

```yaml
---
collections:
  - name: bodsch.core
```

The python module dependencies are not installed by `ansible-galaxy`.  They can
be manually installed using pip:

```bash
pip install -r requirements.txt
```

## Using this collection


You can either call modules by their Fully Qualified Collection Name (FQCN), such as `bodsch.core.remove_ansible_backups`, 
or you can call modules by their short name if you list the `bodsch.core` collection in the playbook's `collections` keyword:

```yaml
---
- name: remove older ansible backup files
  bodsch.core.remove_ansible_backups:
    path: /etc
    holds: 4
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-collection-core/tags)!


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
