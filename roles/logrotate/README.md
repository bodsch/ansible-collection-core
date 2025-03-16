
# Ansible Role:  `bodsch.core.logrotate`

Installs logrotate and provides an easy way to setup additional logrotate scripts by
specifying a list of directives.

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

## Author

- Bodo Schulz
