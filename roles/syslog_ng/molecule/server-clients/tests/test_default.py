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
        "/etc/syslog-ng/conf.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
    assert d.exists


@pytest.mark.parametrize(
    "files",
    [
        "/etc/syslog-ng/syslog-ng.conf",
        "/etc/syslog-ng/conf.d/sources.conf",
        "/etc/syslog-ng/conf.d/destinations.conf",
        "/etc/syslog-ng/conf.d/filters.conf",
        "/etc/syslog-ng/conf.d/logs.conf",
    ],
)
def test_files(host, files):
    f = host.file(files)
    assert f.is_file
    assert f.exists


def test_version(host):
    config_file = "/etc/syslog-ng/syslog-ng.conf"
    content = host.file(config_file).content_string

    _facts = local_facts(host=host, fact="syslog_ng")
    version = _facts.get("version")

    assert f"@version: {version}" in content


def test_service(host):

    _facts = local_facts(host=host, fact="syslog_ng")
    service_unit = _facts.get("service_unit")
    service = host.service(service_unit)
    assert service.is_enabled
    assert service.is_running
