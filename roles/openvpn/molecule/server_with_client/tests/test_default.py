# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="openvpn")

def test_files(host, get_vars):
    """ """
    files = ["/bin/easyrsa"]

    for file in files:
        f = host.file(file)
        assert f.is_file
