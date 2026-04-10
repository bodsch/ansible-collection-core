# Ansible Collection - bodsch.core

Documentation for the collection.

This collection aims to offer an set of ansible modules or helper functions.

## supported Operating systems

Tested on

* ArchLinux
* Debian based
    - Debian 10 / 11 / 12 / 13
    - Ubuntu 20.04 / 22.04 / 24.04

> **RedHat-based systems are no longer officially supported! May work, but does not have to.**


## Requirements & Dependencies

- `dnspython`
- `dirsync`
- `netaddr`

```bash
pip install dnspython
pip install dirsync
pip install netaddr
```

## Included content


### Roles

| Role                                                                       | Build State | Description |
|:---------------------------------------------------------------------------| :---------: | :----       |
| [bodsch.core.pacman](./roles/pacman/README.md)                             | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/pacman.yml?branch=main)][pacman] | Ansible role to configure pacman. |
| [bodsch.core.fail2ban](./roles/fail2ban/README.md)                         | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/fail2ban.yml?branch=main)][fail2ban] | Installs and configure fail2ban |
| [bodsch.core.syslog_ng](./roles/syslog_ng/README.md)                       | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/syslog_ng.yml?branch=main)][syslog_ng] | Installs and configures a classic syslog-ng service for processing log files away from journald. |
| [bodsch.core.logrotate](./roles/logrotate/README.md)                       | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/logrotate.yml?branch=main)][logrotate] | Installs logrotate and provides an easy way to setup additional logrotate scripts |
| [bodsch.core.mount](./roles/mount/README.md)                               | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/mount.yml?branch=main)][mount] | Manage generic mountpoints |
| [bodsch.core.openvpn](./roles/openvpn/README.md)                           | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/openvpn.yml?branch=main)][openvpn] | Ansible role to install and configure openvpn server. |
| [bodsch.core.sysctl](./roles/sysctl/README.md)                             | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/sysctl.yml?branch=main)][sysctl] | Ansible role to configure sysctl. |
| [bodsch.core.sshd](./roles/sshd/README.md)                                 | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/sshd.yml?branch=main)][sshd] | Ansible role to configure sshd. |
| [bodsch.core.bash_aliases](./roles/bash_aliases/README.md)                 | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-core/bash_aliases.yml?branch=main)][bash_aliases] | Ansible role to manage bash aliases and functions. |

[pacman]: https://github.com/bodsch/ansible-collection-core/actions/workflows/pacman.yml
[fail2ban]: https://github.com/bodsch/ansible-collection-core/actions/workflows/fail2ban.yml
[snakeoil]: https://github.com/bodsch/ansible-collection-core/actions/workflows/snakeoil.yml
[syslog_ng]: https://github.com/bodsch/ansible-collection-core/actions/workflows/syslog_ng.yml
[logrotate]: https://github.com/bodsch/ansible-collection-core/actions/workflows/logrotate.yml
[mount]: https://github.com/bodsch/ansible-collection-core/actions/workflows/mount.yml
[openvpn]: https://github.com/bodsch/ansible-collection-core/actions/workflows/openvpn.yml
[sysctl]: https://github.com/bodsch/ansible-collection-core/actions/workflows/sysctl.yml
[sshd]: https://github.com/bodsch/ansible-collection-core/actions/workflows/sshd.yml
[bash_aliases]: https://github.com/bodsch/ansible-collection-core/actions/workflows/bash_aliases.yml

### Modules

| Name                      | Description |
|:--------------------------|:----|
| [bodsch.core.aur](./plugins/modules/aur.py)                                         | Installing packages for ArchLinux with aur |
| [bodsch.core.check_mode](./plugins/modules/check_mode.py)                           | Replacement for `ansible_check_mode`. |
| [bodsch.core.facts](./plugins/modules/facts.py)                                     | Creates a facts file for ansible. |
| [bodsch.core.remove_ansible_backups](./plugins/modules/remove_ansible_backups.py)   | Remove older backup files created by ansible |
| [bodsch.core.package_version](./plugins/modules/package_version.py)                 | Attempts to determine the version of a package to be installed or already installed. |
| [bodsch.core.sync_directory](./plugins/modules/sync_directory.py)                   | Syncronises directories similar to rsync |
| [bodsch.core.easyrsa](.plugins/modules/easyrsa.py)                                  | Manage a Public Key Infrastructure (PKI) using EasyRSA. |
| [bodsch.core.openvpn_client_certificate](.plugins/modules/openvpn_client_certificate.py) | Manage OpenVPN client certificates using EasyRSA. |
| [bodsch.core.openvpn_crl](.plugins/modules/openvpn_crl.py)                          |  |
| [bodsch.core.openvpn_ovpn](.plugins/modules/openvpn_ovpn.py)                        |  |
| [bodsch.core.openvpn](.plugins/modules/openvpn.py)                                  |  |
| [bodsch.core.openvpn_version](.plugins/modules/openvpn_version.py)                  |  |
| [bodsch.core.pip_requirements](.plugins/modules/pip_requirements.py)                | This modules creates an requirement file to install python modules via pip. |
| [bodsch.core.syslog_cmd](.plugins/modules/syslog_cmd.py)                            | Run syslog-ng with arbitrary command-line parameters |
| [bodsch.core.apt_sources](.plugins/modules/apt_sources.py)                          | Manage APT deb822 (.sources) repositories with repo-specific keyrings. |
| [bodsch.core.account_defaults](.plugins/modules/account_defaults.py)                | Resolve account defaults and primary group information. |
| [bodsch.core.bash_aliases](.plugins/modules/bash_aliases.py)                        | Ansible module to manage bash aliases and functions for many users efficiently. |
| [bodsch.core.find_files](.plugins/modules/find_files.py)                            | Ansible module to collect file status information for multiple paths. |


### Module utils

| Name                      | Description |
|:--------------------------|:----|
| [bodsch.core.passlib_bcrypt5_compat](./plugins/module_utils/passlib_bcrypt5_compat.py) | Compatibility helpers for using `passlib` 1.7.4 with `bcrypt` 5.x |
| [bodsch.core.atomic_file](./plugins/module_utils/atomic_file.py)                       | atomic file replacement. |



### Actions

| Name                      | Description |
|:--------------------------|:----|
| [bodsch.core.deploy_and_activate](./plugins/sction/deploy_and_activate.py) | Controller-side orchestration for deploying versioned binaries and activating them via symlinks. |


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
    # version: ">=2.8.x"
```

The python module dependencies are not installed by `ansible-galaxy`.  They can
be manually installed using pip:

```bash
pip install -r requirements.txt
```

## Using this collection


You can either call modules by their Fully Qualified Collection Name (FQCN), such as `bodsch.core.remove_ansible_backups`, 
or you can call modules by their short name if you list the `bodsch.core` collection in the playbook's `collections` keyword:


## Examples

### `bodsch.core.aur`

```yaml
- name: install collabora package via aur
  become: true
  become_user: aur_builder
  bodsch.core.aur:
    state: present
    name: collabora-online-server
    repository: "{{ collabora_arch.source_repository }}"
  async: 3200
  poll: 10
  register: _collabora_installed
```

### `bodsch.core.check_mode`

```yaml
- name: detect ansible check_mode
  bodsch.core.check_mode:
  register: _check_mode

- name: define check_mode
  ansible.builtin.set_fact:
    check_mode: '{{ _check_mode.check_mode }}'
```

### `bodsch.core.deploy_and_activate`

```yaml
- name: deploy and activate logstream_exporter version {{ logstream_exporter_version }}
  bodsch.core.deploy_and_activate:
    src_dir: "{{ logstream_exporter_local_tmp_directory }}"
    install_dir: "{{ logstream_exporter_install_path }}"
    link_dir: "/usr/bin"
    remote_src: false # "{{ 'true' if logstream_exporter_direct_download else 'false' }}"
    owner: "{{ logstream_exporter_system_user }}"
    group: "{{ logstream_exporter_system_group }}"
    mode: "0755"
    items:
      - name: "{{ logstream_exporter_release.binary }}"
        capability: "cap_net_raw+ep"
  notify:
    - restart logstream exporter
```

### `bodsch.core.easyrsa`

```yaml
- name: initialize easy-rsa - (this is going to take a long time)
  bodsch.core.easyrsa:
    pki_dir: '{{ openvpn_easyrsa.directory }}/pki'
    req_cn_ca: "{{ openvpn_certificate.req_cn_ca }}"
    req_cn_server: '{{ openvpn_certificate.req_cn_server }}'
    ca_keysize: 4096
    dh_keysize: "{{ openvpn_diffie_hellman_keysize }}"
    working_dir: '{{ openvpn_easyrsa.directory }}'
    force: true
  register: _easyrsa_result
```

### `bodsch.core.facts`

```yaml
- name: create custom facts
  bodsch.core.facts:
    state: present
    name: icinga2
    facts:
      version: "2.10"
      salt: fgmklsdfnjyxnvjksdfbkuser
      user: icinga2
```

### `bodsch.core.openvpn_client_certificate`

```yaml
- name: create or revoke client certificate
  bodsch.core.openvpn_client_certificate:
    clients:
      - name: molecule
        state: present
        roadrunner: false
        static_ip: 10.8.3.100
        remote: server
        port: 1194
        proto: udp
        device: tun
        ping: 20
        ping_restart: 45
        cert: molecule.crt
        key: molecule.key
        tls_auth:
          enabled: true
      - name: roadrunner_one
        state: present
        roadrunner: true
        static_ip: 10.8.3.10
        remote: server
        port: 1194
        proto: udp
        device: tun
        ping: 20
        ping_restart: 45
        cert: roadrunner_one.crt
        key: roadrunner_one.key
        tls_auth:
          enabled: true
    working_dir: /etc/easy-rsa
```

### `bodsch.core.openvpn_crl`

```yaml
- name: Check CRL status and include revoked certificates
  bodsch.core.openvpn_crl:
    state: status
    pki_dir: /etc/easy-rsa/pki
    list_revoked_certificates: true

- name: Warn if CRL expires within 14 days
  bodsch.core.openvpn_crl:
    state: status
    pki_dir: /etc/easy-rsa/pki
    warn_for_expire: true
    expire_in_days: 14
  register: crl_status

- name: Regenerate (renew) CRL using Easy-RSA
  bodsch.core.openvpn_crl:
    state: renew
    pki_dir: /etc/easy-rsa/pki
    working_dir: /etc/easy-rsa
  register: crl_renew
```

### `bodsch.core.openvpn_ovpn`

```yaml
- name: Force recreation of an existing .ovpn file
  bodsch.core.openvpn_ovpn:
    state: present
    username: carol
    destination_directory: /etc/openvpn/clients
    force: true
```

### `bodsch.core.openvpn_version`

```yaml
- name: Print parsed version
  ansible.builtin.debug:
    msg: "OpenVPN version: {{ openvpn.version }}"
```

### `bodsch.core.openvpn`

```yaml
- name: Generate tls-auth key (ta.key)
  bodsch.core.openvpn:
    state: genkey
    secret: /etc/openvpn/ta.key

- name: Generate tls-auth key only if marker does not exist
  bodsch.core.openvpn:
    state: genkey
    secret: /etc/openvpn/ta.key
    creates: /var/lib/openvpn/ta.key.created

- name: Force regeneration by removing marker first
  bodsch.core.openvpn:
    state: genkey
    secret: /etc/openvpn/ta.key
    creates: /var/lib/openvpn/ta.key.created
    force: true

- name: Create Easy-RSA client and write inline .ovpn
  bodsch.core.openvpn:
    state: create_user
    secret: /dev/null              # required by module interface, not used here
    username: alice
    destination_directory: /etc/openvpn/clients
    chdir: /etc/easy-rsa

- name: Create user only if marker does not exist
  bodsch.core.openvpn:
    state: create_user
    secret: /dev/null
    username: bob
    destination_directory: /etc/openvpn/clients
    chdir: /etc/easy-rsa
    creates: /var/lib/openvpn/clients/bob.created
```

### `bodsch.core.package_version`

```yaml
- name: get version of available package
  bodsch.core.package_version:
    package_name: nano
  register: package_version
```

### `bodsch.core.pip_requirements`

```yaml
- name: create pip requirements file
  bodsch.core.pip_requirements:
    name: docker
    state: present
    requirements:
      - name: docker
        compare_direction: "=="
        version: 6.0.0

      - name: setuptools
        version: 39.1.0

      - name: requests
        versions:
          - ">= 2.28.0"
          - "< 2.30.0"
          - "!~ 1.1.0"
  register: pip_requirements
```

### `bodsch.core.remove_ansible_backups`

```yaml
---
- name: remove older ansible backup files
  bodsch.core.remove_ansible_backups:
    path: /etc
    holds: 4
```

### `bodsch.core.sync_directory`

```yaml
- name: syncronize config for first run
  bodsch.core.sync_directory:
    source_directory: "{{ nextcloud_install_base_directory }}/nextcloud/{{ nextcloud_version }}/config_DIST"
    destination_directory: "{{ nextcloud_install_base_directory }}/nextcloud/config"
    arguments:
      verbose: true
      purge: false
```

### `bodsch.core.syslog_cmd`

```yaml
- name: detect config version
  bodsch.core.syslog_cmd:
    parameters:
      - --version
  when:
    - not running_in_check_mode
  register: _syslog_config_version

- name: validate syslog-ng config
  bodsch.core.syslog_cmd:
    parameters:
      - --syntax-only
  check_mode: true
```


### `bodsch.core.bash_aliases`

```yaml
- name: Manage bash aliases/functions for many users in one task
  become: true
  bodsch.core.bash_aliases:
    state: present
    backup: true
    fail_on_error: true
    common_aliases:
      - alias: ll
        command: "ls -lah"
    users:
      - name: alice
        aliases:
          - alias: foo
            command: "echo 'foo'"
        functions:
          - name: mkcd
            content: |
              mkdir -p "$1" && cd "$1"
      - name: bob
        manage_bashrc: true
        aliases: []
        functions: []
```

### `bodsch.core.find_files`

```yaml
- name: Collect file information for multiple paths
  bodsch.core.find_files:
    file_list:
      - /etc/passwd
      - /etc/shadow
      - /does/not/exist
      
- name: Use SHA-512 for checksums
  bodsch.core.find_files:
    names:
      - /etc/hosts
      - /etc/resolv.conf
    get_checksum: true
    checksum_algorithm: sha512
```



### `bodsch.core.atomic_file`

```yaml
from ansible_collections.bodsch.php.plugins.module_utils.atomic_file import AtomicFileWriter

try:
    with AtomicFileWriter(
        destination=data_file,
        mode="w",
        encoding="utf-8",
    ) as file_handle:
        file_handle.write(data)

    exists = data_path.exists()

    if not exists:
        raise OSError(
            f"Atomic write reported success, but destination is missing: {data_file}"
        )

    os.chmod(data_file, 0o0664)

except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
    self.module.log(f"ERROR: Atomic file write failed: {exc}")
    raise
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
