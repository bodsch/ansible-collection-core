import pytest
import os
import yaml
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')


@pytest.fixture()
def AnsibleDefaults():
    with open("../../defaults/main.yml", 'r') as stream:
        return yaml.load(stream)


@pytest.mark.parametrize("dirs", [
    "/etc/fail2ban",
    "/etc/fail2ban/action.d",
    "/etc/fail2ban/filter.d",
    "/etc/fail2ban/jail.d",
])
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
    assert d.exists


@pytest.mark.parametrize("files", [
    "/etc/fail2ban/fail2ban.conf",
    "/etc/fail2ban/jail.conf",
    "/etc/fail2ban/jail.local",
])
def test_files(host, files):
    f = host.file(files)
    assert f.exists
    assert f.is_file
