# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="client")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="openvpn")


def test_files(host, get_vars):
    """ """
    files = [
        "/etc/openvpn/client/molecule.conf",
        "/etc/openvpn/keys/molecule/ca.crt",
        "/etc/openvpn/keys/molecule/molecule.crt",
        "/etc/openvpn/keys/molecule/molecule.key",
        "/etc/openvpn/keys/molecule/ta.key",
    ]

    for file in files:
        f = host.file(file)
        assert f.is_file

def test_service(host, get_vars):
    """ """
    distribution = host.system_info.distribution

    service = host.service("openvpn-client@molecule")

    if distribution == "artix":
        service = host.service("openvpn.molecule")

    assert service.is_enabled

    if not distribution == "artix":
        assert service.is_running
