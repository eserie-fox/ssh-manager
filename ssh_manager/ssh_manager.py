import json
import stat
from typing import List
from ssh_manager.utils.config import Config
import ssh_manager.ssh_config.parser as parser
import ssh_manager.ssh_config.builder as builder
import os
import git
import shutil


class SSHManager:

    def __init__(self, config_path: str):
        self.config = Config(config_path)
        self.ssh_key_repo_config = None

    def get_ssh_directory(self) -> str:
        return self.config.data()["ssh_dir"]

    def get_abs_path_based_on_ssh_key_repo_config(self, relevant_path: str) -> str:
        return self.config.to_abs_path_based_on_local_repo(relevant_path)

    def get_ssh_config_path(self) -> str:
        return os.path.normpath(
            os.path.expanduser(os.path.join(self.get_ssh_directory(), "config"))
        ).replace("\\", "/")

    def get_ssh_key_list(self) -> List:
        ignore = {"authorized_keys", "config", "known_hosts", "known_hosts.old"}
        res = os.listdir(self.get_ssh_directory())
        ret = []
        for filename in res:
            if os.path.basename(filename) in ignore or os.path.basename(
                filename
            ).endswith(".pub"):
                continue
            ret.append(filename)
        return ret

    def pull_ssh_key_repo(self):
        remote_repo = self.config.data()["ssh_key_remote_repo"]
        local_repo = os.path.expanduser(self.config.data()["ssh_key_local_repo"])

        if os.path.exists(local_repo):
            # 通过获取Git仓库的信息检查URL是否一致
            repo = git.Repo(local_repo)
            current_url = repo.remotes.origin.url
            if current_url != remote_repo:
                raise ValueError(
                    f"Mismatch repo url, local path {local_repo} url={current_url}, remote url={remote_repo}"
                )
            repo.remotes.origin.pull()
        else:
            os.makedirs(local_repo)
            git.Repo.clone_from(remote_repo, local_repo)
        self.read_ssh_key_repo_config()

    def read_ssh_key_repo_config(self):
        with open(
            self.config.data()["ssh_key_local_repo"] + "/config.json",
            "r",
            encoding="utf-8",
        ) as file:
            config = json.load(file)
            self.ssh_key_repo_config = {}
            for server in config:
                self.ssh_key_repo_config[server["ServerName"]] = server

    def parse_current_ssh_config(self):
        if not os.path.exists(self.get_ssh_config_path()):
            return []
        with open(self.get_ssh_config_path(), "r", encoding="utf-8") as file:
            return parser.parse_ssh_config(file.read())

    def get_ssh_key_repo_server_names(self) -> List[str]:
        names = list(self.ssh_key_repo_config.keys())
        return names

    def generate_ssh_config(
        self, server_name: str, endpoint_id: int = 0, auth_id: int = 0
    ) -> builder.SSHHostConfig:
        if server_name not in self.ssh_key_repo_config:
            raise ValueError(f"Unknown server name: {server_name}")
        server = self.ssh_key_repo_config[server_name]

        choice = builder.SSHHostConfigChoice(self, server, endpoint_id, auth_id)
        ssh_host_config = builder.SSHHostConfig(choice=choice)

        return ssh_host_config

    def delete_identify_file(self, ssh_host_config: builder.SSHHostConfig):
        identify_file = ssh_host_config.get_ssh_identity_file()
        if identify_file is None:
            return
        identify_file = os.path.expanduser(identify_file)
        if os.path.isfile(identify_file):
            os.remove(identify_file)
        dir_name = os.path.dirname(identify_file)

        if not os.listdir(dir_name):
            os.rmdir(dir_name)

    def copy_identify_file(self, ssh_host_config: builder.SSHHostConfig):
        original_identify_file = ssh_host_config.get_ssh_original_identity_file()
        if original_identify_file is None:
            return
        original_identify_file = os.path.expanduser(original_identify_file)

        identify_file = os.path.expanduser(ssh_host_config.get_ssh_identity_file())
        assert (original_identify_file is None) == (
            identify_file is None
        ), "identify_file and original_identify_file should be both None or not None"

        if original_identify_file is not None:
            # 检查 identify_file 路径是否存在，如果不存在则新建文件夹
            if not os.path.exists(os.path.dirname(identify_file)):
                os.makedirs(os.path.dirname(identify_file), exist_ok=True)
            # 确保 original_identify_file 路径存在，否则raise Exception
            if not os.path.exists(original_identify_file):
                raise ValueError(
                    f"original_identify_file not exists: {original_identify_file}"
                )
            # 复制文件并设置权限
            shutil.copy2(original_identify_file, identify_file)
            os.chmod(identify_file, stat.S_IRUSR | stat.S_IWUSR)

    def append_ssh_host_config(self, ssh_host_config: builder.SSHHostConfig):
        self.copy_identify_file(ssh_host_config)
        ssh_config = self.get_ssh_config_path()
        if not os.path.exists(ssh_config):
            os.makedirs(os.path.dirname(ssh_config), exist_ok=True)
            with open(ssh_config, "w", encoding="utf-8") as file:
                file.write("# This file is managed by ssh_manager\n")
                print("Config not exists, created")

        with open(ssh_config, "a", encoding="utf-8") as file:
            file.write("\n\n")
            file.write(ssh_host_config.to_string(0))
            # print("Config updated")
