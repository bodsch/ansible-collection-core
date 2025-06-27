
# Ansible Role:  `bodsch.core.pacman`

Ansible role to configure pacman.

## supported Operating systems

* ArchLinux
* ArtixLinux

## Configuration

There are pre-defined values for [Arch Linux](vars/archlinux.yml) and [Artix Linux](vars/artixlinux.yml).

```yaml
pacman_config: {}

pacman_options: {}

pacman_repositories: {}

pacman_mirrors: {}

pacman_custom_mirrors: []
```

### `pacman_config`

[documentation](https://archlinux.org/pacman/pacman.conf.5.html#_options)

```yaml
pacman_config:
  root_dir: "/"
  db_path: /var/lib/pacman/
  cache_dir: /var/cache/pacman/pkg/
  log_file: /var/log/pacman.log
  gpg_dir: /etc/pacman.d/gnupg/
  hook_dir: /etc/pacman.d/hooks/
  hold_pkg:
    - pacman
    - glibc
  xfer_command: /usr/bin/curl -s -L -C - -f -o %o %u
  clean_method: KeepInstalled
  architecture: auto
  ignore_pkg: []
  ignore_group: []
  no_upgrade: []
  no_extract: []

  use_syslog: true
  color: true
  no_progress_bar: true
  check_space: true
  verbose_pkg_lists: false
  parallel_downloads: 5

  sig_level:
    - Required
    - DatabaseOptional
  local_file_sig_level:
    - Optional
  remote_file_sig_level:
    - Required
```

### `pacman_config`

```yaml
pacman_options:
  no_extract:
    - "usr/share/help/* !usr/share/help/en*"
    - "usr/share/gtk-doc/html/* usr/share/doc/*"
    - "usr/share/locale/* usr/share/X11/locale/* usr/share/i18n/*"
    - "!*locale*/en*/* !usr/share/i18n/charmaps/UTF-8.gz !usr/share/*locale*/locale.*"
    - "!usr/share/*locales/en_?? !usr/share/*locales/i18n* !usr/share/*locales/iso*"
    - "!usr/share/*locales/trans*"
    - "usr/share/man/* usr/share/info/*"
    - "usr/share/vim/vim*/lang/*"
```

### `pacman_repositories`

[documentation](https://archlinux.org/pacman/pacman.conf.5.html#_repository_sections)

[Package and Database Signature Checking](https://archlinux.org/pacman/pacman.conf.5.html#_package_and_database_signature_checking_a_id_sc_a)

[Artix Support](https://wiki.artixlinux.org/Main/Repositories)

[cleaning old repositories](https://archlinux.org/news/cleaning-up-old-repositories/)


```yaml
pacman_repositories:
  custom:
    enabled: false
    sig_level:
      - Optional
      - TrustAll
    server: file:///home/custompkgs
    usage:
      - All

  core:
    enabled: true
    include: /etc/pacman.d/mirrorlist

  extra:
    enabled: true
    include: /etc/pacman.d/mirrorlist

  community-testing:
    enabled: false
    include: /etc/pacman.d/mirrorlist

  community:
    enabled: false
    include: /etc/pacman.d/mirrorlist
```

### `pacman_mirrors`


```yaml
pacman_mirrors:
  "Default mirrors":
    enabled: true
    servers:
      - https://geo.mirror.pkgbuild.com/$repo/os/$arch
      - https://mirror.rackspace.com/archlinux/$repo/os/$arch
      - https://mirror.leaseweb.net/archlinux/$repo/os/$arch

  "Europe - Germany":
    enabled: true
    servers:
      - https://mirror.netcologne.de/artix-linux/$repo/os/$arch
      - http://mirrors.redcorelinux.org/artixlinux/$repo/os/$arch
      - https://mirror.pascalpuffke.de/artix-linux/$repo/os/$arch
      - https://ftp.uni-bayreuth.de/linux/artix-linux/$repo/os/$arch
```

### `pacman_custom_mirrors`

```yaml
pacman_custom_mirrors:
  - file: /etc/pacman.d/mirrorlist-arch
    "ARCH MIRRORS":
      enabled: false
      servers:
        - http://mirror.i3d.net/pub/archlinux/$repo/os/$arch
```

---

## Author and License

- Bodo Schulz
