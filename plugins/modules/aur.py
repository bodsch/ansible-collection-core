#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url

import re
import json
import tarfile
import os
import os.path
import urllib.parse

from pathlib import Path
__metaclass__ = type

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: aur
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Installing packages for ArchLinux with aur

description:
    - This modules manages packages for ArchLinux on a target with aur (like M(ansible.builtin.yum), M(ansible.builtin.apt), ...).

options:
  state:
    description:
      - Whether to install (C(present)), or remove (C(absent)) a package.
    required: true
  repository:
    description:
      - Name of the repository from which the code for aur is obtained.
      - This is usually a Git repository listed under U(https://aur.archlinux.org).
    type: str
    required: true
  name:
    description:
      - Package name under which the result is installed.
    type: str
    required: true
"""

EXAMPLES = """
- name: install icinga2 package via aur
  become: true
  become_user: aur_builder
  bodsch.core.aur:
    state: present
    name: icinga2
    repository: https://aur.archlinux.org/icinga2.git
  register: _icinga2_installed
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class Aur():
    """
      Main Class
    """
    module = None

    def __init__(self, module):
        """

        """
        self.module = module
        self.state = module.params.get("state")
        self.name = module.params.get("name")
        self.repository = module.params.get("repository")

        self.pacman_binary = self.module.get_bin_path('pacman', True)
        self.git_binary = self.module.get_bin_path('git', True)

    def run(self):
        """
          runner
        """
        installed, installed_version = self.package_installed(self.name)

        self.module.log(msg=f"  {self.name} is installed: {installed} / {installed_version}")

        if installed and self.state == "absent":
            sudo_binary = self.module.get_bin_path('sudo', True)

            args = []
            args.append(sudo_binary)
            args.append(self.pacman_binary)
            args.append("--remove")
            args.append("--cascade")
            args.append("--recursive")
            args.append("--noconfirm")
            args.append(self.name)

            rc, _, err = self._exec(args)

            if rc == 0:
                return dict(
                    changed=True,
                    msg=f"Package {self.name} succesfull removed."
                )
            else:
                return dict(
                    failed=True,
                    changed=False,
                    msg=f"An error occurred while removing the package {self.name}: {err}"
                )

        if self.state == "present":
            if self.repository:
                rc, out, err, changed = self.install_from_repository(installed_version)

                if rc == 99:
                    msg = out
                    rc = 0
                else:
                    msg = f"package {self.name} succesfull installed."

            else:
                rc, out, err, changed = self.install_from_aur()

            if rc == 0:
                return dict(
                    failed=False,
                    changed=changed,
                    msg=msg
                )
            else:
                return dict(
                    failed=True,
                    msg=err
                )

        return dict(
            failed=False,
            changed=False,
            msg="It's all right. Keep moving! There is nothing to see!"
        )

    def package_installed(self, package):
        """
          Determine if the package is already installed
        """
        # self.module.log(msg=f"package_installed({package})")

        args = []
        args.append(self.pacman_binary)
        args.append("--query")
        args.append(package)

        rc, out, _ = self._exec(args, check=False)

        version_string = None
        if out:
            pattern = re.compile(r"icinga2 (?P<version>.*)-.*", re.MULTILINE)

            version = re.search(pattern, out)
            if version:
                version_string = version.group('version')

        return (rc == 0, version_string)

    def run_makepkg(self, directory):
        """
          run makepkg to build and install pakage
        """
        self.module.log(msg=f"run_makepkg({directory})")
        self.module.log(msg=f"  current dir : {os.getcwd()}")

        local_directory = os.path.exists(directory)

        if not local_directory:
            rc = 1
            out = None
            err = f"no directory {directory} found"
        else:
            makepkg_binary = self.module.get_bin_path('makepkg', required=True)

            args = []
            args.append(makepkg_binary)
            args.append("--syncdeps")
            args.append("--install")
            args.append("--noconfirm")
            args.append("--needed")
            args.append("--clean")

            rc, out, err = self._exec(args, check=False)

        return (rc, out, err)

    def install_from_aur(self):
        """
          use repository for installation
        """
        import tempfile

        _url = f'https://aur.archlinux.org/rpc/?v=5&type=info&arg={urllib.parse.quote(self.name)}'

        self.module.log(msg=f"  url {_url}")

        f = open_url(_url)

        result = json.dumps(json.loads(f.read().decode('utf8')))

        self.module.log(msg=f"  result {result}")

        if result['resultcount'] != 1:
            return (1, '', f'package {self.name} not found')

        result = result['results'][0]

        self.module.log(msg=f"  result {result}")

        f = open_url(f"https://aur.archlinux.org/{result['URLPath']}")

        with tempfile.TemporaryDirectory() as tmpdir:

            tar = tarfile.open(mode='r|*', fileobj=f)
            tar.extractall(tmpdir)
            tar.close()

            rc, out, err = self.run_makepkg(str(Path.home()))

        return (rc, out, err, True)

    def install_from_repository(self, installed_version):
        """
          use repository for installation

          return:
            tupple (rc, out, err, changed)
        """
        os.chdir(str(Path.home()))
        # self.module.log(msg="  current dir : {}".format(os.getcwd()))

        local_directory = os.path.exists(self.name)

        if not local_directory:
            rc, out, err = self.git_clone(repository=self.repository)

            if rc != 0:
                err = "can't run 'git clone ...'"
                return (rc, out, err, False)

        os.chdir(self.name)

        if os.path.exists(".git"):
            """
              we can update the current repository
            """
            rc, out, err = self.git_pull()

            if rc != 0:
                err = "can't run 'git pull ...'"
                return (rc, out, err, False)

                # return dict(
                #     failed=True,
                #     msg="can't run 'git pull ...'",
                #     error=err
                # )

        pkgbuild_file = "PKGBUILD"
        if not os.path.exists(pkgbuild_file):
            """
              whaaaat?
            """
            err = "can't found PKGBUILD"
            return (1, None, err, False)

            # return dict(
            #     failed=True,
            #     msg="can't found PKGBUILD"
            # )

        """
          read first 10 lines of file
        """
        with open(pkgbuild_file) as myfile:
            lines = [next(myfile) for x in range(10)]

        data = "".join(lines)
        pattern = re.compile(r"pkgver=(?P<version>.*)", re.MULTILINE)

        package_version = ""
        version = re.search(pattern, data)

        if version:
            package_version = version.group('version')

        if installed_version == package_version:
            return (99, f"Version {installed_version} is already installed.", None, False)
            # return dict(
            #     changed=False,
            #     msg=f"Version {installed_version} are installed."
            # )

        self.module.log(msg=f"new version: {package_version}")

        """
          package does not seem to be installed ...
          here we go ...
        """
        rc, out, err = self.run_makepkg(str(Path.home()))

        return (rc, out, err, True)

    def git_clone(self, repository):
        """
          simply git clone ...
        """
        if not self.git_binary:
            return (1, None, "not git found")

        args = []
        args.append(self.git_binary)
        args.append("clone")
        args.append(repository)
        args.append(self.name)

        rc, out, err = self._exec(args)

        return (rc, out, err)

    def git_pull(self):
        """
          simply git clone ...
        """
        if not self.git_binary:
            return (1, None, "git not found")

        args = []
        args.append(self.git_binary)
        args.append("pull")

        rc, out, err = self._exec(args)

        return (rc, out, err)

    def _exec(self, cmd, check=False):
        """
          execute shell commands
        """
        rc, out, err = self.module.run_command(cmd, check_rc=check)

        if rc != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return (rc, out, err)


# ===========================================
# Module execution.
#


def main():

    args = dict(
        state=dict(
            default="present",
            choices=["present", "absent"]
        ),
        repository=dict(
            type='str',
            required=True
        ),
        name=dict(
            type='str',
            required=True
        )
    )
    module = AnsibleModule(
        argument_spec=args,
        # mutually_exclusive=[['name', 'upgrade']],
        # required_one_of=[['name', 'upgrade']],
        supports_check_mode=False,
    )

    aur = Aur(module)
    result = aur.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
