
# Ansible Role:  `logrotate`

Installs logrotate and provides an easy way to setup additional logrotate scripts by
specifying a list of directives.


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-logrotate/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-logrotate)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-logrotate)][releases]
[![Ansible Quality Score](https://img.shields.io/ansible/quality/50067?label=role%20quality)][quality]

[ci]: https://github.com/bodsch/ansible-logrotate/actions
[issues]: https://github.com/bodsch/ansible-logrotate/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-logrotate/releases
[quality]: https://galaxy.ansible.com/bodsch/logrotate


## Requirements & Dependencies

Ansible Collections

- [bodsch.core](https://github.com/bodsch/ansible-collection-core)

```bash
ansible-galaxy collection install bodsch.core
```
or
```bash
ansible-galaxy collection install --requirements-file collections.yml
```


### Operating systems

Tested on

* ArchLinux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

> **RedHat-based systems are no longer officially supported! May work, but does not have to.**


## usage

```yaml
logrotate_global:
  rotate_log: weekly
  rotate_size: ''
  su_user: ''
  su_group: ''
  rotate: 2
  create: true
  dateext: true
  compress: true
  tabooext: []
  archive_directory: ''

logrotate_conf_dir: "/etc/logrotate.d"

logrotate_scripts: {}

logroate_disable_systemd: true
```

###  **logrotate_scripts**: A dictionary of logrotate scripts and the directives to use for the rotation.

* `state` - create (`present`) or remove (`absent`) configuration. default: `present`
* `path` - Path to point logrotate to for the log rotation
* `paths` - A list of paths to point logrotate to for the log rotation.
* `options` - List of directives for logrotate, view the logrotate man page for specifics
* `scripts` - Dict of scripts for logrotate (see Example below)

```yaml
logrotate_scripts:
  audit:
    path: /var/log/audit/audit.log
    description: |
      rotate all audit logs
    options:
      - weekly
      - rotate 4
      - missingok
      - notifempty
      - delaycompress
    scripts:
      prerotate: systemctl stop auditd.service > /dev/null
      postrotate: systemctl start auditd.service > /dev/null
      foo: failed
```

```yaml
logrotate_scripts:
  nginx:
    paths:
      - /var/log/nginx/*/*.log
      - /var/log/nginx/*.log
    options:
      - weekly
      - rotate 2
      - missingok
      - notifempty
      - compress
      - sharedscripts
      - create 0644 http log
      - su root http
    scripts:
      postrotate: test ! -r /run/nginx.pid || kill -USR1 $(cat /run/nginx.pid)
```

## Example Playbook

see into [molecule test](molecule/default/converge.yml) and [configuration](molecule/default/group_vars/all/vars.yml)


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-logrotate/tags)!



## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
