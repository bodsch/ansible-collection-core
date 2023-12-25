
# Ansible Role:  `fail2ban`

An Ansible Role that installs and configure fail2ban 2.x on Debian/Ubuntu, ArchLinux and ArtixLinux (mabybe also on other `openrc` based Systemes).

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-fail2ban/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-fail2ban)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-fail2ban)][releases]
[![Ansible Quality Score](https://img.shields.io/ansible/quality/50067?label=role%20quality)][quality]

[ci]: https://github.com/bodsch/ansible-fail2ban/actions
[issues]: https://github.com/bodsch/ansible-fail2ban/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-fail2ban/releases
[quality]: https://galaxy.ansible.com/bodsch/fail2ban


## Requirements & Dependencies

None

### Operating systems

Tested on

* ArchLinux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

> **RedHat-based systems are no longer officially supported! May work, but does not have to.**


## Role Variables

Available variables are listed below, along with default values (see `defaults/main.yaml`):

`fail2ban_ignoreips`

can be an IP address, a CIDR mask or a DNS host.

`fail2ban_conf`

`fail2ban_jail`

`fail2ban_path_definitions`

`fail2ban_jails`

`fail2ban_jail`


## Example Playbook

see into [molecule test](molecule/default/converge.yml) and [configuration](molecule/default/group_vars/all/vars.yml)



```yaml
fail2ban_ignoreips:
  - 127.0.0.1/8
  - 192.168.0.0/24

fail2ban_conf:
  default:
    loglevel: INFO
    logtarget: "/var/log/fail2ban.log"
    syslogsocket: auto
    socket: /run/fail2ban/fail2ban.sock
    pidfile: /run/fail2ban/fail2ban.pid
    dbfile: /var/lib/fail2ban/fail2ban.sqlite3
    dbpurgeage: 1d
    dbmaxmatches: 10
  definition: {}
  thread:
    stacksize: 0

fail2ban_jail:
  default:
    ignoreips: "{{ fail2ban_ignoreips }}"
    bantime: 600
    maxretry: 3
    findtime: 3200
    backend: auto
    usedns: warn
    logencoding: auto
    jails_enabled: false
  actions:
    destemail: root@localhost
    sender: root@localhost
    mta: sendmail
    protocol: tcp
    chain: INPUT
    banaction: iptables-multiport

fail2ban_jails:
  - name: ssh
    enabled: true
    port: ssh
    filter: sshd
    logpath: /var/log/authlog.log
    findtime: 3200
    bantime: 86400
    maxretry: 2
  - name: ssh-breakin
    enabled: true
    port: ssh
    filter: sshd-break-in
    logpath: /var/log/authlog.log
    maxretry: 2
  - name: ssh-ddos
    enabled: true
    port: ssh
    filter: sshd-ddos
    logpath: /var/log/authlog.log
    maxretry: 2
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-fail2ban/tags)!


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
