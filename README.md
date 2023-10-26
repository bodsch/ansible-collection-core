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

```sh
#> ansible-galaxy collection install bodsch.core
```

To install directly from GitHub:

```sh
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

```sh
#> pip install -r requirements.txt
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
