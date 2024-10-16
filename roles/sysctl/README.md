# Ansible Role:  `sysctl`

Configure sysctl on your system.


### Operating systems

Tested on

* ArchLinux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

> **RedHat-based systems are no longer officially supported! May work, but does not have to.**



## Role Variables

```yaml
sysctl_directory: /etc/sysctl.d

sysctl_rules:
  - name: sshd
    rules:
      net.ipv4.ip_nonlocal_bind: 1
      net.ipv6.ip_nonlocal_bind: 1
  - name: openvpn
    rules:
      net.ipv4.ip_forward: 1
      
sysctl_reload: true      
```


---

## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
