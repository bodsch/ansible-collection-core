# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="fail2ban")

@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/fail2ban",
        "/etc/fail2ban/action.d",
        "/etc/fail2ban/filter.d",
        "/etc/fail2ban/jail.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory


@pytest.mark.parametrize(
    "files",
    [
        "/etc/fail2ban/fail2ban.conf",
        "/etc/fail2ban/jail.conf",
        "/etc/fail2ban/jail.local",
    ],
)
def test_files(host, files):
    f = host.file(files)
    assert f.is_file
