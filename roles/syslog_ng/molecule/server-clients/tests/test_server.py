# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="syslog_ng")


def test_open_port(host):
    """ """
    for i in host.socket.get_listening_sockets():
        print(i)

    assert host.socket("udp://0.0.0.0:514").is_listening
    assert host.socket("tcp://10.19.0.10:5140").is_listening
    assert host.socket("udp://10.19.0.10:5140").is_listening
