# Ansible Role:  `bodsch.core.bash_aliases`

Manage generic bash aliases


## Role Variables

```yaml
# Zieluser (Default: aktueller Remote-User)
bash_alias_target_user: "{{ ansible_user_id }}"

# Was soll verwaltet werden?
bash_alias_manage_aliases: true
bash_alias_manage_functions: true
bash_alias_manage_bashrc: true

# Optional: absolute Pfade überschreiben (leer = wird aus HOME + filename berechnet)
bash_alias_aliases_path: ""
bash_alias_functions_path: ""
bash_alias_bashrc_path: ""

# Dateinamen (falls *_path nicht gesetzt)
bash_alias_aliases_filename: ".bash_aliases"
bash_alias_functions_filename: ".bash_functions"
bash_alias_bashrc_filename: ".bashrc"

# Rechte
bash_alias_mode: "0644"
bash_alias_bashrc_mode: "0644"

# Daten
bash_alias_aliases: []
bash_alias_functions: []
```

---

## Author

- Bodo Schulz
