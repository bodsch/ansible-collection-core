# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

def merge_two_dicts(x, y):
    z = x.copy() # start with keys and values of x
    z.update(y)  # modifies z with keys and values of y
    return z

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="openvpn")


def test_easyrsa(host, get_vars):
    """ """
    files = ["/bin/easyrsa"]

    for file in files:
        f = host.file(file)
        assert f.exists
        assert f.is_file


def test_files(host, get_vars):
    """ """
    files = [
        "/etc/openvpn/server/server.conf",
        "/etc/openvpn/keys/server/ca.crt",
        "/etc/openvpn/keys/server/dh2048.pem",
        "/etc/openvpn/keys/server/instance.crt",
        "/etc/openvpn/keys/server/instance.key",
        "/etc/openvpn/keys/server/ta.key",
    ]

    for file in files:
        f = host.file(file)
        assert f.is_file


def test_service(host, get_vars):
    """ """
    distribution = host.system_info.distribution

    service = host.service(get_vars.get("openvpn_service_name"))

    if distribution == "artix":
        service = host.service("openvpn")

    print(f"service: {service}")

    assert service.is_enabled
    assert service.is_running


def test_open_port(host, get_vars):
    """ """
    _defaults = get_vars.get("openvpn_defaults_server")
    _configure = get_vars.get("openvpn_server")
    data = merge_two_dicts(_defaults, _configure)

    proto = data.get("proto")
    port = data.get("port")
    listen_ip = data.get("listen_ip", None)

    if not listen_ip:
        listen_ip = "0.0.0.0"

    service = host.socket(f"{proto}://{listen_ip}:{port}")
    assert service.is_listening
