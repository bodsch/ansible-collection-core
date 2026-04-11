# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="bash_aliases")

@pytest.mark.parametrize("dirs", ["/home/bob","/home/alice"])
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory

@pytest.mark.parametrize("files", [
    "/home/alice/.bash_aliases",
    "/home/alice/.bash_functions",
    "/home/bob/.bash_aliases",
    "/home/bob/.bash_functions",
])
def test_files(host, files):

    d = host.file(files)
    assert d.is_file
