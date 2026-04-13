# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="mount")


@pytest.mark.parametrize("files", ["/etc/fstab"])
def test_files(host, files):

    d = host.file(files)
    assert d.is_file
