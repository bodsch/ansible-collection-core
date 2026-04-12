# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="logrotate")


@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/logrotate.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory


@pytest.mark.parametrize(
    "files",
    [
        "/etc/logrotate.conf",
        "/etc/logrotate.d/nofunc",
        "/etc/logrotate.d/audit",
        "/etc/logrotate.d/system",
        "/etc/logrotate.d/icinga2",
    ],
)
def test_files(host, files):
    f = host.file(files)
    assert f.is_file


def test_service(host):
    """ """
    timer = host.file("/usr/lib/systemd/system/logrotate.timer")

    if timer.exists:
        service = host.service("logrotate.timer")
        assert not service.is_enabled
