#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

from ansible.module_utils import distro
from ansible.module_utils.basic import AnsibleModule

import re

__metaclass__ = type

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: package_version
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: Attempts to determine the version of a package to be installed or already installed.

description:
    - Attempts to determine the version of a package to be installed or already installed.
    - Supports apt, pacman, dnf (or yum) as package manager.

options:
  state:
    description:
      - The status of a package.
      - Defines whether the version of an already installed (C(installed)) package or the
        version of a package available for installation (C(available)) is output.
    default: available
    required: true
  repository:
    description:
      - Name of the repository in which the search is being conducted.
      - This is only necessary for RedHat-based distributions.
    type: str
    default: ""
    required: false
  package_name:
    description:
      - Package name which is searched for in the system or via the package management.
    type: str
    required: true
"""

EXAMPLES = r"""
- name: get version of available package
  bodsch.core.package_version:
    package_name: nano
  register: package_version

- name: get version of available mariadb-server
  bodsch.core.package_version:
    state: available
    package_name: mariadb-server
  register: package_version

- name: get version of installed php-fpm
  bodsch.core.package_version:
    package_name: php-fpm
    state: installed
  register: package_version

- name: detect available mariadb version for RedHat based
  bodsch.core.package_version:
    state: available
    package_name: mariadb-server
    repository: MariaDB
  register: package_version
  when:
    - ansible_os_family | lower == 'redhat'
    - mariadb_use_external_repo
"""

RETURN = r"""
full_version:
    description:
        - Version String
    type: string
platform_version:
    description:
        - Version String with major and minor Part (e.g. 8.1)
    type: string
major_version:
    description:
        - major Version (e.g. 8)
    type: string
version_string_compressed:
    description:
        - Compressed variant of (C(platform_version)) (e.g. 81).
        - Only needed for RedHat-based distributions.
    type: string
"""

# ---------------------------------------------------------------------------------------


class PackageVersion(object):
    """
    """

    def __init__(self, module):

        self.module = module

        self.state = module.params.get("state")
        self.package_name = module.params.get("package_name")
        self.package_version = module.params.get("package_version")
        self.repository = module.params.get("repository")

        self.distribution = distro.id()
        self.version = distro.version()
        self.codename = distro.codename()

        self.module.log(msg=f"  - pkg       : {self.distribution} - {self.version} - {self.codename}")

    def run(self):
        """
        """
        version = ''
        error = True
        msg = f"unknown or unsupported distribution: '{self.distribution}'"

        if self.distribution.lower() in ["debian", "ubuntu"]:
            error, version, msg = self._search_apt()

        if self.distribution.lower() in ["arch", "artix"]:
            error, version, msg = self._search_pacman()

        if self.distribution.lower() in ["centos", "oracle", "redhat", "fedora", "rocky", "almalinux"]:
            error, version, msg = self._search_yum()

        if error:
            return dict(
                failed=True,
                available_versions=version,
                msg=msg
            )

        if version is not None:
            major_version = None
            minor_version = None
            platform_version = None

            version_splitted = version.split(".")

            # self.module.log(msg=f"  - version_splitted  : {version_splitted}")
            major_version = version_splitted[0]

            if len(version_splitted) > 1:
                minor_version = version_splitted[1]

            if minor_version:
                platform_version = '.'.join([major_version, minor_version])
            else:
                platform_version = major_version

            version = dict(
                full_version=version,
                platform_version=platform_version,
                major_version=major_version,
                version_string_compressed=version.replace('.', '')
            )

        result = dict(
            failed=error,
            available=version,
            msg=msg
        )

        return result

    def _search_apt(self):
        """
          support apt
        """
        import apt

        pkg = None

        cache = apt.cache.Cache()

        # try:
        #     cache.update()
        # except SystemError as error:
        #     self.module.log(msg=f"error         : {error}")
        #     raise FetchFailedException(error)
        # if not res and raise_on_error:
        #     self.module.log(msg="FetchFailedException()")
        #     raise FetchFailedException()
        # else:
        #     cache.open()

        try:
            cache.update()
            cache.open()
        except SystemError as error:
            self.module.log(msg=f"error         : {error}")
            return False, None, f"package {self.package_name} is not installed"
        except Exception as error:
            self.module.log(msg=f"error         : {error}")

        try:
            pkg = cache[self.package_name]
            version_string = None

            # debian:10 / buster:
            #  [php-fpm=2:7.3+69]
            # ubuntu:20.04 / focal
            #  [php-fpm=2:7.4+75]
            # debian:9 : 1:10.4.20+maria~stretch'
            # debian 10: 1:10.4.20+maria~buster
            #
        except KeyError as error:
            self.module.log(msg=f"error         : {error}")
            return False, None, f"package {self.package_name} is not installed"

        if pkg:
            # self.module.log(msg=f"  - pkg       : {pkg} ({type(pkg)})")
            # self.module.log(msg=f"  - installed : {pkg.is_installed}")
            # self.module.log(msg=f"  - shortname : {pkg.shortname}")
            # self.module.log(msg=f"  - versions  : {pkg.versions}")
            # self.module.log(msg=f"  - versions  : {pkg.versions[0]}")

            pkg_version = pkg.versions[0]
            version = pkg_version.version

            if version[1] == ":":
                pattern = re.compile(r"(?<=\:)(?P<version>.*?)(?=[-+])")
            else:
                pattern = re.compile(r"(?P<version>.*?)(?=[-+])")

            result = re.search(pattern, version)
            version_string = result.group('version')

            # self.module.log(msg=f"  - version_string  : {version_string}")
        return False, version_string, ""

    def _search_yum(self):
        """
          support dnf and - as fallback - yum
        """
        package_mgr = self.module.get_bin_path('dnf', False)

        if (not package_mgr):
            package_mgr = self.module.get_bin_path('yum', True)

        if (not package_mgr):
            return True, "", "no valid package manager (yum or dnf) found"

        package_version = self.package_version

        if (package_version):
            package_version = package_version.replace('.', '')

        args = []
        args.append(package_mgr)

        args.append("info")
        args.append(self.package_name)

        if self.repository:
            args.append("--disablerepo")
            args.append("*")
            args.append("--enablerepo")
            args.append(self.repository)

        rc, out, err = self.module.run_command(
            args,
            check_rc=False)

        version = ''

        if rc == 0:
            versions = []

            pattern = re.compile(r".*Version.*: (?P<version>.*)", re.MULTILINE)
            # pattern = re.compile(
            #     r"^{0}[0-9+].*\.x86_64.*(?P<version>[0-9]+\.[0-9]+)\..*@(?P<repo>.*)".format(self.package_name),
            #     re.MULTILINE
            # )

            for line in out.splitlines():
                self.module.log(msg=f"  line     : {line}")
                for match in re.finditer(pattern, line):
                    result = re.search(pattern, line)
                    versions.append(result.group('version'))

            self.module.log(msg=f"versions      : '{versions}'")

            if len(versions) == 0:
                msg = 'nothing found'
                error = True

            if len(versions) == 1:
                msg = ''
                error = False
                version = versions[0]

            if len(versions) > 1:
                msg = 'more then one result found! choose one of them!'
                error = True
                version = ', '.join(versions)
        else:
            msg = f"package {self.package_name} not found"
            error = False
            version = None

        return error, version, msg

    def _search_pacman(self):
        """
            pacman support
            pacman --noconfirm --sync --search php7 | grep -E "^(extra|world)\\/php7 (.*)\\[installed\\]" | cut -d' ' -f2
        """
        pacman_bin = self.module.get_bin_path('pacman', True)

        version = None
        args = []
        args.append(pacman_bin)

        if self.state == "installed":
            args.append("--query")
        else:
            args.append("--noconfirm")
            args.append("--sync")

        args.append("--search")
        args.append(self.package_name)

        rc, out, err = self._pacman(args)

        if rc == 0:
            pattern = re.compile(
                # r'^(?P<repository>core|extra|community|world|local)\/{}[0-9\s]*(?P<version>\d\.\d).*-.*'.format(self.package_name),
                r'^(?P<repository>core|extra|community|world|local)\/{} (?P<version>\d+(\.\d+){{0,2}}(\.\*)?)-.*'.format(self.package_name),
                re.MULTILINE
            )

            result = re.search(pattern, out)

            msg = ''
            error = False
            version = result.group('version')

        else:
            msg = f"package {self.package_name} not found"
            error = False
            version = None

        return error, version, msg

    def _pacman(self, cmd):
        """
          support pacman
        """
        rc, out, err = self.module.run_command(cmd, check_rc=False)

        if rc != 0:
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err

# ---------------------------------------------------------------------------------------
# Module execution.
#


def main():

    args = dict(
        state=dict(
            choices=[
                "installed",
                "available",
            ],
            default="available"
        ),
        package_name=dict(
            required=True,
            type='str'
        ),
        package_version=dict(
            required=False,
            default=''
        ),
        repository=dict(
            required=False,
            default=""
        )
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    result = PackageVersion(module).run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
