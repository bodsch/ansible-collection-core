
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
    allowipv6: ""
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

fail2ban_filters: []
fail2ban_actions: []
```

### `fail2ban_filters`

```yaml
fail2ban_filters:
  - name: sshd-break-in
    author: bodsch
    definition:
      failregex:
        - 'sshd\[\S*\]: Address <HOST> (.*) POSSIBLE BREAK-IN ATTEMPT!'
      ignoreregex: ''

  - name: sshd-unknown-user
    author: bodsch
    description: |
      The regex should math against

      # Invalid user <USER> from <HOST> port 54520
      # Connection closed by invalid user <USER> <HOST> port 54520 [preauth]
    includes:
      before: common.conf
    definition:
      daemon: sshd
      failregex:
        - '^[iI]nvalid user <F-USER>.*?</F-USER> (?:from )?<HOST>'
        - '^Connection closed by invalid user <F-USER>.*?</F-USER>?<HOST>'
      ignoreregex: ''

  - name: sshd-ddos
    author: bodsch
    description: |
      The regex here also relates to a exploit:

      http://www.securityfocus.com/bid/17958/exploit
      The example code here shows the pushing of the exploit straight after
      reading the server version. This is where the client version string normally
      pushed. As such the server will read this unparsible information as
      "Did not receive identification string".
    includes:
      before: common.conf
    definition:
      daemon: sshd
      failregex:
        - '^%(__prefix_line)sDid not receive identification string from <HOST>\s*$'
      ignoreregex: ''

  - name: nginx-botsearch
    author: Frantisek Sumsal
    description: |
      Fail2Ban filter to match web requests for selected URLs that don't exist

      DEV Notes:
      Based on apache-botsearch filter
    includes:
      before: botsearch-common.conf
    definition:
      failregex:
        - '^<HOST> \- \S+ \[\] \"(GET|POST|HEAD) \/<block> \S+\" 404 .+$'
        - '^ \[error\] \d+#\d+: \*\d+ (\S+ )?\"\S+\" (failed|is not found) \(2\: No such file or directory\), client\: <HOST>\, server\: \S*\, request: \"(GET|POST|HEAD) \/<block> \S+\"\, .*?$'
      ignoreregex: ''
      datepattern:
        - '{^LN-BEG}%%ExY(?P<_sep>[-/.])%%m(?P=_sep)%%d[T ]%%H:%%M:%%S(?:[.,]%%f)?(?:\s*%%z)?'
        - '^[^\[]*\[({DATE})'
        - '{^LN-BEG}'
```

### `fail2ban_actions`

```yaml
fail2ban_actions:
  - name: iptables-common
    includes:
      after:
        - iptables-blocktype.local
        - iptables-common.local
    definition:
      actionflush:
        - '<iptables> -F f2b-<name>'

    init:
      name: default
      chain: INPUT
      port: ssh
      #  Values:  [ tcp | udp | icmp | all ] Default: tcp
      protocol: tcp
      blocktype: 'REJECT --reject-with icmp-port-unreachable'
      returntype: RETURN
      lockingopt: '-w'
      iptables: 'iptables <lockingopt>'
    init_ipv6:
      blocktype: 'REJECT --reject-with icmp6-port-unreachable'
      iptables: 'ip6tables <lockingopt>'

  - name: iptables
    includes:
      before: iptables-common.conf
    definition:
      actionstart:
        - '<iptables> -N f2b-<name>'
        - '<iptables> -A f2b-<name> -j <returntype>'
        - '<iptables> -I <chain> -p <protocol> --dport <port> -j f2b-<name>'
      actionstop:
        - '<iptables> -D <chain> -p <protocol> --dport <port> -j f2b-<name>'
        - '<actionflush>'
        - '<iptables> -X f2b-<name>'
      actioncheck:
        - '<iptables> -n -L <chain> | grep -q "f2b-<name>[ \t]"'
      actionban:
        - '<iptables> -I f2b-<name> 1 -s <ip> -j <blocktype>'
      actionunban:
        - '<iptables> -D f2b-<name> -s <ip> -j <blocktype>'

  - name: ufw
    author: Guilhem Lettron
    description: |
      Fail2Ban action configuration file for ufw

      You are required to run "ufw enable" before this will have any effect.

      The insert position should be appropriate to block the required traffic.
      A number after an allow rule to the application won't be of much use.

      Enhancements: Daniel Black

    definition:
      actionstart:
      actionstop:
      actioncheck:
      actionban:
        - '[ -n "<application>" ] && app="app <application>"'
        - 'ufw insert <insertpos> <blocktype> from <ip> to <destination> $app'
      actionunban:
        - '[ -n "<application>" ] && app="app <application>"'
        - 'ufw delete <blocktype> from <ip> to <destination> $app'
    init:
      insertpos: 1
      blocktype: reject
      destination: any
      application: ''
```

## Author

- Bodo Schulz
