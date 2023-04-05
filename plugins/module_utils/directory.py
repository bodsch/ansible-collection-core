#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

import os
import pwd
import grp

from ansible_collections.bodsch.core.plugins.module_utils.lists import find_in_list


def create_directory(directory, owner=None, group=None, mode=None):
    """
    """
    try:
        os.makedirs(directory, exist_ok=True)
    except FileExistsError:
        pass

    if mode is not None:
        os.chmod(directory, int(mode, base=8))

    if owner is not None:
        try:
            owner = pwd.getpwnam(owner).pw_uid
        except KeyError:
            owner = int(owner)
            pass
    else:
        owner = 0

    if group is not None:
        try:
            group = grp.getgrnam(group).gr_gid
        except KeyError:
            group = int(group)
            pass
    else:
        group = 0

    os.chown(directory, int(owner), int(group))

    if os.path.isdir(directory):
        return True
    else:
        return False


def create_directory_tree(directory_tree, current_state):
    """
    """
    for entry in directory_tree:
        """
        """
        source = entry.get('source')
        source_handling = entry.get('source_handling', {})
        force_create = source_handling.get('create', None)
        force_owner = source_handling.get('owner', None)
        force_group = source_handling.get('group', None)
        force_mode = source_handling.get('mode', None)

        curr = find_in_list(current_state, source)

        current_owner = curr[source].get('owner')
        current_group = curr[source].get('group')

        # create directory
        if force_create is not None and not force_create:
            pass
        else:
            try:
                os.makedirs(source, exist_ok=True)
            except FileExistsError:
                pass

        # change mode
        if os.path.isdir(source) and force_mode is not None:
            if isinstance(force_mode, int):
                mode = int(str(force_mode), base=8)
            if isinstance(force_mode, str):
                mode = int(force_mode, base=8)

            os.chmod(source, mode)

        # change ownership
        if force_owner is not None or force_group is not None:
            """
            """
            if os.path.isdir(source):
                """
                """
                if force_owner is not None:
                    try:
                        force_owner = pwd.getpwnam(str(force_owner)).pw_uid
                    except KeyError:
                        force_owner = int(force_owner)
                        pass
                elif current_owner is not None:
                    force_owner = current_owner
                else:
                    force_owner = 0

                if force_group is not None:
                    try:
                        force_group = grp.getgrnam(str(force_group)).gr_gid
                    except KeyError:
                        force_group = int(force_group)
                        pass
                elif current_group is not None:
                    force_group = current_group
                else:
                    force_group = 0

                os.chown(source, int(force_owner), int(force_group))


def permstr_to_octal(modestr, umask):
    '''
        Convert a Unix permission string (rw-r--r--) into a mode (0644)
    '''
    revstr = modestr[::-1]
    mode = 0
    for j in range(0, 3):
        for i in range(0, 3):
            if revstr[i + 3 * j] in ['r', 'w', 'x', 's', 't']:
                mode += 2 ** (i + 3 * j)

    return (mode & ~umask)


def current_state(directory):
    """
    """
    current_owner = None
    current_group = None
    current_mode = None

    if os.path.isdir(directory):
        _state = os.stat(directory)
        try:
            current_owner = pwd.getpwuid(_state.st_uid).pw_uid
        except KeyError:
            pass

        try:
            current_group = grp.getgrgid(_state.st_gid).gr_gid
        except KeyError:
            pass

        try:
            current_mode = oct(_state.st_mode)[-4:]
        except KeyError:
            pass

    return current_owner, current_group, current_mode


def fix_ownership(directory, force_owner=None, force_group=None, force_mode=False):
    """
    """
    changed = False
    error_msg = None

    if os.path.isdir(directory):
        current_owner, current_group, current_mode = current_state(directory)

        # change mode
        if force_mode is not None and force_mode != current_mode:
            try:
                if isinstance(force_mode, int):
                    mode = int(str(force_mode), base=8)
            except Exception as e:
                error_msg = f" - ERROR '{e}'"

            try:
                if isinstance(force_mode, str):
                    mode = int(force_mode, base=8)
            except Exception as e:
                error_msg = f" - ERROR '{e}'"

            os.chmod(directory, mode)

        # change ownership
        if force_owner is not None or force_group is not None and (force_owner != current_owner or force_group != current_group):
            if force_owner is not None:
                try:
                    force_owner = pwd.getpwnam(str(force_owner)).pw_uid
                except KeyError:
                    force_owner = int(force_owner)
                    pass
            elif current_owner is not None:
                force_owner = current_owner
            else:
                force_owner = 0

            if force_group is not None:
                try:
                    force_group = grp.getgrnam(str(force_group)).gr_gid
                except KeyError:
                    force_group = int(force_group)
                    pass
            elif current_group is not None:
                force_group = current_group
            else:
                force_group = 0

            os.chown(
                directory,
                int(force_owner),
                int(force_group)
            )

        _owner, _group, _mode = current_state(directory)

        if (current_owner != _owner) or (current_group != _group) or (current_mode != _mode):
            changed = True

    return changed, error_msg
