
# Ansible Role:  `bodsch.core.sshd`

## usage

```yaml
sshd_config:
  port:                                             # 22
    - 22
  address_family: any
  listen_address: []
    # - "0.0.0.0:22"
    # - "127.0.1.1:22622"
  # https://man.openbsd.org/sshd_config#RekeyLimit
  rekey_limit: []                                   # ['default', 'none']
    # - default
    # - none
  syslog_facility: AUTH                             #
  log_level: INFO                                   #
  log_verbose: []                                   # 'kex.c:*:1000,*:kex_exchange_identification():*,packet.c:*'
  login_grace_time: ""                              # 2m
  permit_root_login: prohibit-password
  strict_modes: true
  max_auth_tries: ""                                # 6
  max_sessions: ""                                  # 10
  pubkey_authentication: true

  # Expect .ssh/authorized_keys2 to be disregarded by default in future.
  authorized_keys_file:
    - "/etc/ssh/authorized_keys/%u"  
    - .ssh/authorized_keys

  authorized_principals_file: ""                    # false

  authorized_keys_command: ""                       # false
  authorized_keys_command_user: ""                  # false

  # For this to work you will also need host keys in /etc/ssh/ssh_known_hosts
  hostbased_authentication: ""                      # false
  hostbased_accepted_algorithms: ""                 #

  host_certificate: ""
  host_keys:
    - "/etc/ssh/ssh_host_rsa_key"
    - "/etc/ssh/ssh_host_ecdsa_key"
    - "/etc/ssh/ssh_host_ed25519_key"
  host_key_agent: ""                                #
  host_key_algorithms: []                           #

  # Change to yes if you don't trust ~/.ssh/known_hosts for
  # HostbasedAuthentication
  ignore_user_known_hosts: ""                       # false
  # Don't read the user's ~/.rhosts and ~/.shosts files
  ignore_rhosts: ""                                 # true

  # To disable tunneled clear text passwords, change to no here!
  password_authentication: ""                       # true
  permit_empty_passwords: ""                        # false

  # Change to yes to enable challenge-response passwords (beware issues with
  # some PAM modules and threads)
  challenge_response_authentication: ""             # false

  # Kerberos options
  kerberos_authentication: ""                       # false
  kerberos_or_local_passwd: ""                      # true
  kerberos_ticket_cleanup: ""                       # true
  kerberos_get_afs_token: ""                        # false

  kex_algorithms: []

  # GSSAPI options
  gss_api_authentication: ""                        # false
  gss_api_cleanup_credentials: ""                   # true
  gss_api_strict_acceptor_check: ""                 # true
  gss_api_key_exchange: ""                          # false

  # Set this to 'yes' to enable PAM authentication, account processing,
  # and session processing. If this is enabled, PAM authentication will
  # be allowed through the ChallengeResponseAuthentication and
  # PasswordAuthentication.  Depending on your PAM configuration,
  # PAM authentication via ChallengeResponseAuthentication may bypass
  # the setting of "PermitRootLogin without-password".
  # If you just want the PAM account and session checks to run without
  # PAM authentication, then enable this but set PasswordAuthentication
  # and ChallengeResponseAuthentication to 'no'.
  use_pam: true

  allow_agent_forwarding: ""                        # true
  allow_tcp_forwarding: ""                          # true
  gateway_ports: ""                                 # false
  x11_forwarding: ""                                # false
  x11_display_offset: ""                            # 10
  x11_use_localhost: ""                             # true
  permit_tty: ""                                    # true
  print_motd: ""                                    # false
  print_last_log: ""                                # true
  tcp_keep_alive: ""                                # true
  permituser_environment: ""                        # false
  compression: ""                                   # delayed
  client_alive_interval: ""                         # 0
  client_alive_count_max: ""                        # 3
  use_dns: ""                                       # false
  pid_file: ""                                      # /var/run/sshd.pid
  max_startups: ""                                  # 10:30:100
  permit_tunnel: ""                                 # false
  chroot_directory: ""                              # false
  version_addendum: ""                              # false

  # no default banner path
  banner: ""                                        # false
  deny_groups: []
  deny_users: []
  ciphers: []
  macs: []

  # Allow client to pass locale environment variables
  accept_env:
    - LANG
    - LC_*

  # override default of no subsystems
  subsystem:
    name: sftp
    path: "{{ sshd_sftp_server }}"

  # Example of overriding settings on a per-user basis
  match_users:
    - username: anoncvs
      options:
        x11_forwarding: false
        AllowTcpForwarding: false
        PermitTTY: false
        ForceCommand:
          - cvs
          - server

ssh_config:
  - host: "*"
    # ForwardAgent: false
    # ForwardX11: false
    # ForwardX11Trusted: false
    # PasswordAuthentication: true
    # HostbasedAuthentication: ""
    # GSSAPIAuthentication: ""
    # GSSAPIDelegateCredentials: ""
    # GSSAPIKeyExchange: false
    # GSSAPITrustDNS: false
    # BatchMode: false
    # CheckHostIP: true
    # AddressFamily: any
    # ConnectTimeout: 0
    # StrictHostKeyChecking: ask
    # IdentityFile:
    #   - "~/.ssh/id_rsa"
    #   - "~/.ssh/id_dsa"
    #   - "~/.ssh/id_ecdsa"
    #   - "~/.ssh/id_ed25519"
    # Port: 22
    # Ciphers:
    #   - aes128-ctr
    #   - aes192-ctr
    #   - aes256-ctr
    #   - aes128-cbc
    #   - 3des-cbc
    # MACs:
    #   - hmac-md5
    #   - hmac-sha1
    #   - umac-64@openssh.com
    # EscapeChar: "~"
    # Tunnel: false
    # TunnelDevice: "any:any"
    # PermitLocalCommand: false
    # VisualHostKey: false
    # ProxyCommand: ssh -q -W %h:%p gateway.example.com
    # RekeyLimit: 1G 1h
    # UserKnownHostsFile: ~/.ssh/known_hosts.d/%k  
    SendEnv:
      - "LANG LC_*"
    hash_known_hosts: false
```

---

## Author and License

- Bodo Schulz
