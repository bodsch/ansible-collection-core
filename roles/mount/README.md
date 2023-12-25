# Ansible Role:  `mount`

Manage generic mountpoints

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-mount/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-mount)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-mount)][releases]

[ci]: https://github.com/bodsch/ansible-mount/actions
[issues]: https://github.com/bodsch/ansible-mount/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-mount/releases


### Operating systems

Tested on

* ArchLinux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

> **RedHat-based systems are no longer officially supported! May work, but does not have to.**



## Role Variables

```yaml
mount_fstab: /etc/fstab

mount_devices: []

mount_smb_share: []
```

With `mount_fstab` you can specify the fstab file to be generated.
This is especially helpful for tests :)


### `mount_smb_share`

creates passwordfile for smb shares.

```yaml
mount_smb_share:
  - username: "bar"
    password: "foo"
    domain: "WORKSPACE"
    passwordfile: "/tmp/.bar.smbcredentials"
```


### `mount_devices`

|              | required | default    | description |
| :---         | :---:    | :---       | :---        |
| `source`     | **yes**  | `-`        |             |
| `mountpoint` | **yes**  | `-`        |             |
| `fstype`     | **yes**  | `-`        |             |
| `opts`       | **no**   | `defaults` |             |
| `state`      | **no**   | `present`  |             |
| `dump`       | **no**   | `0`        |             |
| `passno`     | **no**   | `0`        |             |
| `fstab`      | **no**   | ``         |             |

## example configuration

```yaml
mount_fstab: /tmp/molecule_fstab

mount_smb_share:
  - username: "bar"
    password: "foo"
    passwordfile: "/tmp/zorg.pass"
  - username: "foo"
    password: "bar"
    passwordfile: "/tmp/foo.pass"

mount_devices:

  - source: tmpfs
    mountpoint: /tmp
    fstype: tmpfs
    opts: auto,rw,noatime,size=250M,nr_inodes=800k
    state: present

  - source: nfs.example.org:/data
    mountpoint: /mnt/remote
    fstype: nfs
    opts: vers=4,noauto,users,soft,intr,rsize=8192,wsize=8192
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-mount/tags)!

---

## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
