
# Ansible Role:  `bodsch.core.snakeoil`

build a simple snakeoil certificate for a test environment.


## config parameters

| Variable             | default    | description |
| :----                | :----      | :----       |
| `snakeoil_extract_to`| `''`       | extract on remote machine |
| `snakeoil_domain`    | `''`       | domain for a certificat (e.g. `bar.local`) |
| `snakeoil_life_time` | `29`       | certificat lifetime in days |
| `snakeoil_alt_names` | `[]`       | an array with alternate names or IPs |
| `snakeoil_dhparam`   | `1024`     | diffie-hellman parameter length |
| `snakeoil_force`     | `false`    | force recreate a certificate (delete the old files) |
| `snakeoil_dn`        | `{}`       | dictionary with configuration parameters |

## default

```yaml
snakeoil_extract_to: ''

snakeoil_domain: ''
snakeoil_email: "cert@{{ snakeoil_domain }}"

snakeoil_life_time: 29

snakeoil_alt_names: []

snakeoil_dhparam: 1024

snakeoil_force: false

snakeoil_dn:
  country: DE
  state: Hamburg
  location: Hamburg
  organisation: ACME Inc.
```

### Alt names

```yaml
snakeoil_alt_names:
  - dns:
      - foo.bar.local
      - www.bar.local
  - ip:
      - 192.168.2.1
```


## manual creation

```bash
cat > csr_details.txt <<-EOF
[req]
default_bits = 4096
prompt = no
default_md = sha512
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C=DE
ST=Hamburg
L=Hamburg
O=Acme, Inc
OU=Testing Domain
emailAddress=cert@cm.local
CN = *.cm.local

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1  = cm.local
DNS.2  = database.cm.local
DNS.3  = backend.cm.local
DNS.4  = frontend.cm.local
DNS.5  = delivery.cm.local
DNS.6  = monitoring.cm.local
DNS.7  = mysql.cm.local
DNS.8  = mongo.cm.local
DNS.9  = *.delivery.cm.local
DNS.10 = *.backend.cm.local
DNS.11 = overview.cm.local
DNS.12 = corporate.cm.local
DNS.13 = studio.cm.local
DNS.14 = preview.cm.local
DNS.15 = *.be.cm.local
DNS.16 = *.fe.cm.local
IP.1   = 192.168.124.10
IP.2   = 192.168.124.20
IP.3   = 192.168.124.30
IP.4   = 192.168.124.35
IP.5   = 192.168.124.50
EOF

# Let’s call openssl now by piping the newly created file in
openssl req -new -sha512 -nodes -out cm.local.csr -newkey rsa:4096 -keyout cm.local.key -config <( cat csr_details.txt )
openssl dhparam -out dh.pem 2048

#
openssl req -noout -verify -in cm.local.csr
openssl req -text -noout -in cm.local.csr

#
openssl x509 -in cm.local.csr -out cm.local.pem -req -signkey cm.local.key -days 365

cat cm.local.key >> cm.local.pem
```


---

## Author and License

- Bodo Schulz
