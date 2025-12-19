# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

import json

from ansible.utils.display import Display

__metaclass__ = type

display = Display()


class FilterModule(object):
    """ """

    def filters(self):
        return {
            "merge_lists": self.merge_lists,
            "sshd_values": self.sshd_values,
        }

    def merge_lists(self, defaults, data):
        """ """
        count_defaults = len(defaults)
        count_data = len(data)

        display.vv(
            "defaults: ({type}) {len} - {data} entries".format(
                data=defaults, type=type(defaults), len=count_defaults
            )
        )
        display.vv(json.dumps(data, indent=2, sort_keys=False))
        display.vv(
            "data    : ({type}) {len} - {data} entries".format(
                data=data, type=type(data), len=count_data
            )
        )

        result = []

        # short way
        if count_defaults == 0:
            return data

        if count_data == 0:
            return defaults

        # our new list from users input
        for d in data:
            _name = d["host"]
            # search the name in the default map
            _defaults_name = self.__search(defaults, _name)
            # display.vv(f"  _defaults_name    : {_defaults_name}")
            # when not found, put these on the new result list
            if not _defaults_name:
                result.append(_defaults_name)
            else:
                # when found, remove these entry from the defaults list, its obsolete
                for i in range(len(defaults)):
                    if defaults[i]["host"] == _name:
                        del defaults[i]
                        break

        # add both lists and sort
        result = data + defaults

        display.vv(f"= result: {result}")

        return result

    def sshd_values(self, data):
        """
        Ersetzt die Keys in einer YAML-Struktur basierend auf einer gegebenen Key-Map.

        :param data: Ansible Datenkonstrukt
        :return: Ansible Datenkonstrukt mit den ersetzten Keys.
        """
        display.vv(f"bodsch.core.sshd_values({data})")

        # Hilfsfunktion zur Rekursion
        def replace_keys(obj):
            """
            :param key_map: Dictionary, das alte Keys mit neuen Keys mappt.
            """
            key_map = {
                "port": "Port",
                "address_family": "AddressFamily",
                "listen_address": "ListenAddress",
                "host_keys": "HostKey",
                "rekey_limit": "RekeyLimit",
                "syslog_facility": "SyslogFacility",
                "log_level": "LogLevel",
                "log_verbose": "LogVerbose",
                "login_grace_time": "LoginGraceTime",
                "permit_root_login": "PermitRootLogin",
                "strict_modes": "StrictModes",
                "max_auth_tries": "MaxAuthTries",
                "max_sessions": "MaxSessions",
                "pubkey_authentication": "PubkeyAuthentication",
                "authorized_keys_file": "AuthorizedKeysFile",
                "authorized_principals_file": "AuthorizedPrincipalsFile",
                "authorized_keys_command": "AuthorizedKeysCommand",
                "authorized_keys_command_user": "AuthorizedKeysCommandUser",
                "hostbased_authentication": "HostbasedAuthentication",
                "hostbased_accepted_algorithms": "HostbasedAcceptedAlgorithms",
                "host_certificate": "HostCertificate",
                "host_key": "HostKey",
                "host_key_agent": "HostKeyAgent",
                "host_key_algorithms": "HostKeyAlgorithms",
                "ignore_user_known_hosts": "IgnoreUserKnownHosts",
                "ignore_rhosts": "IgnoreRhosts",
                "password_authentication": "PasswordAuthentication",
                "permit_empty_passwords": "PermitEmptyPasswords",
                "challenge_response_authentication": "ChallengeResponseAuthentication",
                "kerberos_authentication": "KerberosAuthentication",
                "kerberos_or_local_passwd": "KerberosOrLocalPasswd",
                "kerberos_ticket_cleanup": "KerberosTicketCleanup",
                "kerberos_get_afs_token": "KerberosGetAFSToken",
                "kex_algorithms": "KexAlgorithms",
                "gss_api_authentication": "GSSAPIAuthentication",
                "gss_api_cleanup_credentials": "GSSAPICleanupCredentials",
                "gss_api_strict_acceptor_check": "GSSAPIStrictAcceptorCheck",
                "gss_api_key_exchange": "GSSAPIKeyExchange",
                "use_pam": "UsePAM",
                "allow_agent_forwarding": "AllowAgentForwarding",
                "allow_tcp_forwarding": "AllowTcpForwarding",
                "gateway_ports": "GatewayPorts",
                "x11_forwarding": "X11Forwarding",
                "x11_display_offset": "X11DisplayOffset",
                "x11_use_localhost": "X11UseLocalhost",
                "permit_tty": "PermitTTY",
                "print_motd": "PrintMotd",
                "print_last_log": "PrintLastLog",
                "tcp_keep_alive": "TCPKeepAlive",
                "permituser_environment": "PermitUserEnvironment",
                "compression": "Compression",
                "client_alive_interval": "ClientAliveInterval",
                "client_alive_count_max": "ClientAliveCountMax",
                "ciphers": "Ciphers",
                "deny_groups": "DenyGroups",
                "deny_users": "DenyUsers",
                "macs": "MACs",
                "use_dns": "UseDNS",
                "pid_file": "PidFile",
                "max_startups": "MaxStartups",
                "permit_tunnel": "PermitTunnel",
                "chroot_directory": "ChrootDirectory",
                "version_addendum": "VersionAddendum",
                "banner": "Banner",
                "accept_env": "AcceptEnv",
                "subsystem": "Subsystem",
                "match_users": "Match",
                # ssh_config
                "hash_known_hosts": "HashKnownHosts",
                "send_env": "SendEnv",
                # "": "",
            }

            if isinstance(obj, dict):
                # Ersetze die Keys und rufe rekursiv für die Werte auf
                return {key_map.get(k, k): replace_keys(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                # Falls es eine Liste ist, rekursiv die Elemente bearbeiten
                return [replace_keys(item) for item in obj]
            else:
                return obj

        # Ersetze die Keys im geladenen YAML
        result = replace_keys(data)

        display.v(f"= result: {result}")

        return result

    def __sort_list(self, _list, _filter):
        return sorted(_list, key=lambda k: k.get(_filter))

    def __search(self, d, name):
        res = None
        for sub in d:
            if sub["host"] == name:
                res = sub
                break

        return res
