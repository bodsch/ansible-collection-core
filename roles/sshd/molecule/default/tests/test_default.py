# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="sshd")

@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/ssh",
        "/etc/ssh/ssh_config.d",
        "/etc/ssh/sshd_config.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
    assert d.exists


@pytest.mark.parametrize(
    "files",
    [
        "/etc/ssh/ssh_config",
        "/etc/ssh/sshd_config",
        "/etc/ssh/ssh_host_ecdsa_key",
        "/etc/ssh/ssh_host_ecdsa_key.pub",
        "/etc/ssh/ssh_host_ed25519_key",
        "/etc/ssh/ssh_host_ed25519_key.pub",
        "/etc/ssh/ssh_host_rsa_key",
        "/etc/ssh/ssh_host_rsa_key.pub",
        "/etc/ssh/sshd_config.d/match_users.conf",
        "/etc/ssh/sshd_config.d/subsystem.conf",
    ],
)
def test_files(host, files):
    f = host.file(files)
    assert f.is_file
    assert f.exists


def test_version(host):
    config_file = "/etc/ssh/sshd_config"
    content = host.file(config_file).content_string

    assert "AddressFamily  any" in content


def test_service(host):

    service = host.service("sshd")
    assert service.is_enabled
    assert service.is_running


def test_open_port(host):
    """ """
    for i in host.socket.get_listening_sockets():
        print(i)

    assert host.socket("tcp://0.0.0.0:22").is_listening
