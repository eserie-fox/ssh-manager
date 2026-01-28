import json
import os
import stat
from datetime import datetime
from typing import List, Optional

import git
import ssh_manager.ssh_config.builder as builder
import ssh_manager.ssh_config.parser as parser
from ssh_manager.utils.config import Config
import shutil


class SSHManager:

    def __init__(self, config_path: Optional[str] = None):
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
        env = self._build_git_environment(remote_repo)

        if os.path.exists(local_repo):
            try:
                repo = git.Repo(local_repo)
            except git.exc.InvalidGitRepositoryError as exc:
                if os.path.isdir(local_repo) and not os.listdir(local_repo):
                    shutil.rmtree(local_repo)
                    repo = git.Repo.clone_from(remote_repo, local_repo, env=env)
                else:
                    raise ValueError(
                        f"Local repo path exists but is not a git repository: {local_repo}"
                    ) from exc
        else:
            os.makedirs(os.path.dirname(local_repo), exist_ok=True)
            repo = git.Repo.clone_from(remote_repo, local_repo, env=env)

        repo.git.update_environment(**env)

        if not repo.remotes:
            raise ValueError(f"No remotes configured for local repo: {local_repo}")
        origin = repo.remotes.origin
        current_url = origin.url
        if current_url != remote_repo:
            raise ValueError(
                f"Mismatch repo url, local path {local_repo} url={current_url}, remote url={remote_repo}"
            )

        origin.pull()

        self.read_ssh_key_repo_config()

    def _build_git_environment(self, remote_repo: str) -> dict:
        env = {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "echo",
        }
        if remote_repo.startswith("git@") or remote_repo.startswith("ssh://"):
            env["GIT_SSH_COMMAND"] = (
                "ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
            )
        return env


    def check_ssh_key_repo_config(self) -> bool:
        try:
            config = None
            path = self.config.data()["ssh_key_local_repo"] + "/config.json"
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as file:
                config = json.load(file)
            if not config:
                raise ValueError("Config file is empty")

            config.sort(key=lambda x: x["ServerName"])

            for server in config:
                if not server["ServerName"]:
                    raise ValueError("Server name is empty")
                if "Authentication" in server:
                    auths = server["Authentication"]
                    for auth in auths:
                        if "IdentityFile" in auth:
                            identity_file = auth["IdentityFile"]
                            identity_file = (
                                self.get_abs_path_based_on_ssh_key_repo_config(
                                    identity_file
                                )
                            )
                            if not os.path.exists(identity_file):
                                raise ValueError(
                                    f"Identity file {identity_file} not found"
                                )

            shutil.copy2(path, path + ".bak")

            with open(
                path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(config, file, indent=4)

        except Exception as e:
            print(f"Failed to check ssh key repo config: {e}")
            return False

        print(f"Success to check ssh key repo config")
        return True

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
        if os.path.isdir(dir_name) and not os.listdir(dir_name):
            os.rmdir(dir_name)

    def render_ssh_config(self, configs: List[builder.SSHHostConfig]) -> str:
        """Render a complete ssh config string sorted by host name."""
        sorted_configs = sorted(configs, key=lambda cfg: cfg.name or "")
        lines = ["# This file is managed by ssh_manager"]
        for cfg in sorted_configs:
            lines.append("")
            lines.append(cfg.to_string(0).rstrip())
        lines.append("")
        return "\n".join(lines)

    def write_ssh_config(self, configs: List[builder.SSHHostConfig], backup: bool = True):
        ssh_config = self.get_ssh_config_path()
        os.makedirs(os.path.dirname(ssh_config), exist_ok=True)

        content = self.render_ssh_config(configs)
        tmp_path = f"{ssh_config}.tmp"

        with open(tmp_path, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        if backup and os.path.exists(ssh_config):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{ssh_config}.bak.{timestamp}"
            shutil.copy2(ssh_config, backup_path)

        try:
            os.replace(tmp_path, ssh_config)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

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
            # Ensure identify_file directory exists; create it if needed.
            if not os.path.exists(os.path.dirname(identify_file)):
                os.makedirs(os.path.dirname(identify_file), exist_ok=True)
            # Ensure original_identify_file exists; otherwise raise an exception.
            if not os.path.exists(original_identify_file):
                raise ValueError(
                    f"original_identify_file not exists: {original_identify_file}"
                )
            # Copy file and set permissions.
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
