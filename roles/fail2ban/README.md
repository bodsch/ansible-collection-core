
# Ansible Role:  `bodsch.core.fail2ban`

An Ansible Role that installs and configure fail2ban 2.x on Debian/Ubuntu, ArchLinux and ArtixLinux (mabybe also on other `openrc` based Systemes).

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

## Author

- Bodo Schulz
