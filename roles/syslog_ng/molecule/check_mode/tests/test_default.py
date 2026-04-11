# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="syslog_ng")

@pytest.mark.parametrize(
    "dirs",
    [
        "/etc",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
