#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2022, Bodo Schulz <bodo.schulz@tallence.com>

from __future__ import absolute_import, division, print_function

import os
import time
from contextlib import suppress
import docker
from docker.errors import DockerException
from docker.types import LogConfig


class Container():
    """
    """

    def __init__(self, module):
        """
        """
        self.module = module

        self.module.log("Container::__init__")

        self.docker_client = None

    def client(self):
        """
        """
        self.docker_client = docker.DockerClient(
            base_url='unix://var/run/docker.sock',
            version='auto'
        )
        return self.docker_client

    def log_config(self):
        """
        """
        log_config = LogConfig(
            type=LogConfig.types.JSON,
            config={
                'max-size': '5m',
            }
        )

        return log_config

    def run_container(self, container_image, name, extra_hosts, cmd, env):
        """
        """
        _output = []
        _status_code = 500
        _status_msg = None
        container = None

        self.module.log(
            msg=f"run container with image {container_image} and command {cmd}.")

        if not self.docker_client:
            self.client()

        log_config = self.log_config()

        try:
            container = self.docker_client.containers.run(
                image=container_image,
                hostname=name,
                name=name,
                command=cmd,
                entrypoint="/coremedia/tools/bin/cm",
                log_config=log_config,
                detach=True,
                stdout=True,
                stderr=False,
                remove=True,
                environment=env,
                network="coremedia",
                extra_hosts=extra_hosts
            )

            _status_code = 200
            _status_msg = None

            for line in container.logs(stream=True):
                entry = line.decode('utf-8').strip()

                if "DOCKER ENTRYPOINT" not in entry:
                    _output.append(entry)

        except docker.errors.ContainerError as e:
            # _failed = True
            _status_code = e.status_code
            _status_msg = e.explanation
            self.module.log(f"ERROR (ContainerError) : {_status_code} - {e.explanation}")
        except docker.errors.APIError as e:
            # _failed = True
            _status_code = e.status_code
            _status_msg = e.explanation
            self.module.log(f"ERROR (APIError) : {_status_code} - {e.explanation}")
        except (DockerException, IOError):
            self.module.log(
                msg="[docker]: encountered process error while processing.")
        except Exception as e:
            # _failed = True
            _msg = f"ERROR (Exception) : {str(e)}"
            self.module.log(msg=_msg)
            pass
        finally:
            if container:
                time.sleep(0.5)
                with suppress(DockerException):
                    container.stop()
                container.remove()
            pass

        self.module.log(f"  - output : {_output}")

        return _output, _status_code, _status_msg

    def exec_container(self, container_id, cmd):
        """
        :return:
        """
        self.module.log(f" run command {cmd} inside the container.")

        output = None
        _status_code = 500
        _status_msg = None

        if not self.docker_client:
            self.client()

        log_config = self.log_config()

        try:
            container = self.docker_client.containers.get(id)

            # self.module.log("---- exec_run() --------------")
            _status_code, output = container.exec_run(
                cmd=cmd,
                log_config=log_config,
                detach=False,
            )

            if _status_code == 0:
                """
                """
                _status_code = 200

                # pattern = re.compile(
                #     r".*<h1>CoreMedia Content Feeder Administration</h1><p>(?P<output>.*?)</p>.*")
                #
                # result = re.search(pattern, output.decode('utf-8'))
                # output_string = result.group('output')

                # self.module.log(msg=f" - exit_code : {exit_code}")
                # self.module.log(msg=f" - output    : {output_string}")
            else:
                cmd_string = ' '.join(cmd)
                output = f"There was an error when calling '{cmd_string}'"

        except docker.errors.ContainerError as e:
            # _failed = True
            _status_code = e.status_code
            _status_msg = e.explanation
            self.module.log(f"ERROR (ContainerError) : {_status_code} - {e.explanation}")
        except docker.errors.APIError as e:
            # _failed = True
            _status_code = e.status_code
            _status_msg = e.explanation
            self.module.log(f"ERROR (APIError) : {_status_code} - {e.explanation}")
        except (DockerException, IOError):
            self.module.log(
                msg="[docker]: encountered process error while processing.")
        except Exception as e:
            # _failed = True
            _msg = f"ERROR (Exception) : {str(e)}"
            self.module.log(msg=_msg)
            pass
        finally:
            time.sleep(0.5)
            pass

        self.module.log(f"  - output : {output}")

        return output, _status_code, _status_msg

    def write_environments_file(self):
        """
            sql.store.driver = org.postgresql.Driver
            sql.store.url = jdbc:postgresql://bce-cmpdb-sv04.tik.intern:5432/replication_live_server
            sql.store.user = replication_live_server
            sql.store.password = RdhYNZC6bnx2lzuk9sYFkZ7dTjcGZsaFOrHoqhaVvK
        """
        pass

        # self.environments_file =

    def environments_from_files(self, environments_files=[]):
        """
        """
        lines = []

        for env_file in environments_files:
            if os.path.isfile(env_file):
                self.module.log(f"  - read file: {env_file}")
                with open(env_file) as f:
                    for line in f:
                        # self.module.log(msg=f"  - {line}")
                        if len(line) > 1 and not line.startswith("#") and 'WAIT_HOSTS' not in line:
                            line = line.strip()  # or some other preprocessing
                            lines.append(line)   # storing everything in memory!

        return lines

    def container_images(self, image_name):
        """
        """
        self.module.log(f"Container::container_images({image_name})")

        if not self.docker_client:
            self.client()

        images = {}
        filter = {
            "reference": f"{image_name}"
        }

        try:
            for image in self.docker_client.images.list(filters=filter):
                images.update({
                    image.attrs.get("RepoTags")[0]: image.attrs.get('Id', None)
                })
            return images
        except Exception as e:
            self.module.log(msg=f"ERROR : str({e})")
            pass

        return None

    def list_containers(self):
        """
        """
        self.module.log("Container::list_containers()")

        if not self.docker_client:
            self.client()

        containers = {}
        try:
            for container in self.docker_client.containers.list(all=True):
                containers.update({
                    container.attrs['Id']: container.attrs
                })

            return containers
        except Exception as e:
            self.module.log(msg=f"ERROR : str({e})")
            pass

        return None

    def container(self, container_id):
        """
        """
        self.module.log(f"Container::container({container_id})")

        if not self.docker_client:
            self.client()

        if container_id and container_id.isalnum():
            try:
                for container in self.docker_client.containers.list(all=True, filters={"id": container_id}):
                    return container.attrs

            except Exception as e:
                self.module.log(msg=f"ERROR : str({e})")
                pass

        return None

    def container_search(self, name):
        """
        """
        self.module.log(f"Container::container_search({name})")

        if not self.docker_client:
            self.client()

        all_containers = self.list_containers()
        if all_containers:
            """
            """
            if isinstance(all_containers, dict):
                result = {k: v for k, v in all_containers.items() if v.get('Name', '')[1:] == name}
                if result:
                    container_id = list(result.keys())[0]
                    self.module.log(msg=f"  - {container_id}")
                    return self.container(container_id)

        return None

    def container_restart(self, name):
        """
        :return:
        """
        self.module.log(f"Container::container_restart({name})")

        if not self.docker_client:
            self.client()

        container = self.container_search(self.name)

        if container:
            container_id = container.get("Id", None)

            if container_id:
                for container in self.docker_client.containers.list(all=True, filters={"id": container_id}):
                    container.restart()

                return True, 'restart command completed successfully.'
            else:
                return False, "unknow container id."
        else:
            return False, f"no running feeder {self.rls_name} found."
