# coding: utf-8
from __future__ import unicode_literals

import json
import os

import pytest
import testinfra.utils.ansible_runner
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

HOST = "instance"

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ["MOLECULE_INVENTORY_FILE"]
).get_hosts(HOST)


def pp_json(json_thing, sort=True, indents=2):
    if type(json_thing) is str:
        print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing, sort_keys=sort, indent=indents))
    return None


def base_directory():
    """..."""
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


def read_ansible_yaml(file_name, role_name):
    ext_arr = ["yml", "yaml"]

    read_file = None

    for e in ext_arr:
        test_file = "{}.{}".format(file_name, e)
        if os.path.isfile(test_file):
            read_file = test_file
            break

    return "file={} name={}".format(read_file, role_name)


@pytest.fixture()
def get_vars(host):
    """
    parse ansible variables
    - defaults/main.yml
    - vars/main.yml
    - vars/${DISTRIBUTION}.yaml
    - molecule/${MOLECULE_SCENARIO_NAME}/group_vars/all/vars.yml
    """
    base_dir, molecule_dir = base_directory()
    distribution = host.system_info.distribution

    os = "archlinux"

    print(" -> {} / {}".format(distribution, os))

    file_defaults = read_ansible_yaml(
        "{}/defaults/main".format(base_dir), "role_defaults"
    )
    file_vars = read_ansible_yaml("{}/vars/main".format(base_dir), "role_vars")
    file_distibution = read_ansible_yaml(
        "{}/vars/{}".format(base_dir, os), "role_distibution"
    )
    file_molecule = read_ansible_yaml(
        "{}/group_vars/all/vars".format(base_dir), "test_vars"
    )
    # file_host_molecule = read_ansible_yaml("{}/host_vars/{}/vars".format(base_dir, HOST), "host_vars")

    defaults_vars = (
        host.ansible("include_vars", file_defaults)
        .get("ansible_facts")
        .get("role_defaults")
    )
    vars_vars = (
        host.ansible("include_vars", file_vars).get("ansible_facts").get("role_vars")
    )
    distibution_vars = (
        host.ansible("include_vars", file_distibution)
        .get("ansible_facts")
        .get("role_distibution")
    )
    molecule_vars = (
        host.ansible("include_vars", file_molecule)
        .get("ansible_facts")
        .get("test_vars")
    )
    # host_vars          = host.ansible("include_vars", file_host_molecule).get("ansible_facts").get("host_vars")

    ansible_vars = defaults_vars
    ansible_vars.update(vars_vars)
    ansible_vars.update(distibution_vars)
    ansible_vars.update(molecule_vars)
    # ansible_vars.update(host_vars)

    templar = Templar(loader=DataLoader(), variables=ansible_vars)
    result = templar.template(ansible_vars, fail_on_undefined=False)

    return result


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
