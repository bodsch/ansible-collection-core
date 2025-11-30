import json
import os

import pytest
import testinfra.utils.ansible_runner
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ["MOLECULE_INVENTORY_FILE"]
).get_hosts("instance")


def pp_json(json_thing, sort=True, indents=2):
    if type(json_thing) is str:
        print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing, sort_keys=sort, indent=indents))
    return None


def base_directory():
    cwd = os.getcwd()

    if "group_vars" in os.listdir(cwd):
        directory = "../.."
        molecule_directory = "."
    else:
        directory = "."
        molecule_directory = "molecule/{}".format(
            os.environ.get("MOLECULE_SCENARIO_NAME")
        )

    return directory, molecule_directory


@pytest.fixture()
def get_vars(host):
    """ """
    base_dir, molecule_dir = base_directory()

    file_defaults = "file={}/defaults/main.yml name=role_defaults".format(base_dir)
    file_vars = "file={}/vars/main.yml name=role_vars".format(base_dir)
    file_molecule = "file={}/group_vars/all/vars.yml name=test_vars".format(
        molecule_dir
    )

    defaults_vars = (
        host.ansible("include_vars", file_defaults)
        .get("ansible_facts")
        .get("role_defaults")
    )
    vars_vars = (
        host.ansible("include_vars", file_vars).get("ansible_facts").get("role_vars")
    )
    molecule_vars = (
        host.ansible("include_vars", file_molecule)
        .get("ansible_facts")
        .get("test_vars")
    )

    ansible_vars = defaults_vars
    ansible_vars.update(vars_vars)
    ansible_vars.update(molecule_vars)

    templar = Templar(loader=DataLoader(), variables=ansible_vars)
    result = templar.template(ansible_vars, fail_on_undefined=False)

    return result


@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/logrotate.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
    assert d.exists


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
    assert f.exists
    assert f.is_file


def test_service(host):
    """ """
    timer = host.file("/usr/lib/systemd/system/logrotate.timer")

    if timer.exists:
        service = host.service("logrotate.timer")
        assert not service.is_enabled
