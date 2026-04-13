# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="pacman")


@pytest.mark.parametrize(
    "directories",
    [
        "/etc/pacman.d",
        "/etc/pacman.d/hooks",
    ],
)
def test_directories(host, directories):
    d = host.file(directories)
    assert d.is_directory


@pytest.mark.parametrize(
    "files",
    [
        "/etc/pacman.conf",
        "/etc/pacman.d/mirrorlist",
        "/etc/pacman.d/hooks/linux-modules-post.hook",
        "/etc/pacman.d/hooks/paccache-uninstalled.hook",
    ],
)
def test_files(host, files):
    d = host.file(files)
    assert d.is_file
