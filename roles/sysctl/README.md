# Ansible Role:  `bodsch.core.sysctl`

Configure sysctl on your system.

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
