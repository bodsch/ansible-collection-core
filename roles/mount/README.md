# Ansible Role:  `bodsch.core.mount`

Manage generic mountpoints


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



---

## Author

- Bodo Schulz
