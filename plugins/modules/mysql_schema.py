#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

import os
import warnings

from ansible.module_utils._text import to_native
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mysql import mysql_driver, mysql_driver_fail_msg
from ansible.module_utils.six.moves import configparser

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
module: mysql_schema
version_added: '1.0.15'
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: check the named schema exists in a mysql.

description:
  - check the named schema exists in a mysql (or compatible) database.

options:
  login_user:
    description:
      - user name to login into database.
    type: str
    required: false

  login_password:
    description:
      - password for user name to login into database.
    type: str
    required: false

  login_host:
    description:
      - database hostname
    type: str
    default: 127.0.0.1
    required: false

  login_port:
    description:
      - database port
    type: int
    default: 3306
    required: false

  login_unix_socket:
    description:
      - database socket
    type: str
    required: false

  database_config_file:
    description:
      - optional config file with credentials
    type: str
    required: false

  table_schema:
    description:
      - database schema to check
    type: str
    required: true

  table_name:
    description:
      - optional table name
    type: str
    required: false
"""

EXAMPLES = r"""
- name: ensure, table_schema is present
  bodsch.core.mysql_schema:
    login_host: '::1'
    login_user: root
    login_password: password
    table_schema: icingaweb2

- name: ensure table_schema is created
  bodsch.core.mysql_schema:
    login_host: database
    login_user: root
    login_password: root
    table_schema: icingadb
  register: mysql_icingawebdb_schema
"""

RETURN = r"""
exists:
  description:
    - is the named schema present
  type: bool
changed:
  description: TODO
  type: bool
failed:
  description: TODO
  type: bool
"""

# ---------------------------------------------------------------------------------------


class MysqlSchema(object):
    """ """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        self.login_user = module.params.get("login_user")
        self.login_password = module.params.get("login_password")
        self.login_host = module.params.get("login_host")
        self.login_port = module.params.get("login_port")
        self.login_unix_socket = module.params.get("login_unix_socket")
        self.database_config_file = module.params.get("database_config_file")
        self.table_schema = module.params.get("table_schema")
        self.table_name = module.params.get("table_name")

        self.db_connect_timeout = 30

    def run(self):
        """ """
        if mysql_driver is None:
            self.module.fail_json(msg=mysql_driver_fail_msg)
        else:
            warnings.filterwarnings("error", category=mysql_driver.Warning)

        if not mysql_driver:
            return dict(failed=True, error=mysql_driver_fail_msg)

        state, error, error_message = self._information_schema()

        if error:
            res = dict(failed=True, changed=False, msg=error_message)
        else:
            res = dict(failed=False, changed=False, exists=state)

        return res

    def _information_schema(self):
        """
        get informations about schema

        return:
          state: bool (exists or not)
          count: int
          error: boot (error or not)
          error_message string  error message
        """
        cursor, conn, error, message = self.__mysql_connect()

        if error:
            return None, error, message

        query = f"SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.tables where TABLE_SCHEMA = '{self.table_schema}'"

        try:
            cursor.execute(query)

        except mysql_driver.ProgrammingError as e:
            (errcode, message) = e.args

            message = f"Cannot execute SQL '{query}' : {to_native(e)}"
            self.module.log(msg=f"ERROR: {message}")

            return False, True, message

        records = cursor.fetchall()
        cursor.close()
        conn.close()
        exists = len(records)

        if self.table_name is not None:
            table_names = []
            for e in records:
                table_names.append(e[1])

            if self.table_name in table_names:
                self.module.log(
                    msg=f"  - table name {self.table_name} exists in table schema"
                )

                return True, False, None

        else:
            self.module.log(msg="  - table schema exists")

            if int(exists) >= 4:
                return True, False, None

        return False, False, None

    def __mysql_connect(self):
        """ """
        config = {}

        config_file = self.database_config_file

        if config_file and os.path.exists(config_file):
            config["read_default_file"] = config_file

        # TODO
        # cp = self.__parse_from_mysql_config_file(config_file)

        if self.login_unix_socket:
            config["unix_socket"] = self.login_unix_socket
        else:
            config["host"] = self.login_host
            config["port"] = self.login_port

        # If login_user or login_password are given, they should override the
        # config file
        if self.login_user is not None:
            config["user"] = self.login_user
        if self.login_password is not None:
            config["passwd"] = self.login_password

        if mysql_driver is None:
            self.module.fail_json(msg=mysql_driver_fail_msg)

        try:
            db_connection = mysql_driver.connect(**config)

        except Exception as e:
            message = "unable to connect to database. "
            message += "check login_host, login_user and login_password are correct "
            message += f"or {config_file} has the credentials. "
            message += f"Exception message: {to_native(e)}"

            self.module.log(msg=message)

            return (None, None, True, message)

        return db_connection.cursor(), db_connection, False, "successful connected"

    def __parse_from_mysql_config_file(self, cnf):
        cp = configparser.ConfigParser()
        cp.read(cnf)
        return cp


# ---------------------------------------------------------------------------------------
# Module execution.
#


def main():

    args = dict(
        login_user=dict(type="str"),
        login_password=dict(type="str", no_log=True),
        login_host=dict(type="str", default="127.0.0.1"),
        login_port=dict(type="int", default=3306),
        login_unix_socket=dict(type="str"),
        database_config_file=dict(required=False, type="path"),
        table_schema=dict(required=True, type="str"),
        table_name=dict(required=False, type="str"),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    schema = MysqlSchema(module)
    result = schema.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
