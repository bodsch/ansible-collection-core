# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="sysctl")


@pytest.mark.parametrize(
    "directories",
    [
        "/etc/sysctl.d",
    ],
)
def test_directories(host, directories):

    d = host.file(directories)
    assert d.is_directory


@pytest.mark.parametrize(
    "files",
    [
        "/etc/sysctl.conf",
        # "/etc/sysctl.d/sshd.conf",
        # "/etc/sysctl.d/openvpn.conf",
    ],
)
def test_files(host, files):

    d = host.file(files)
    assert d.is_file
