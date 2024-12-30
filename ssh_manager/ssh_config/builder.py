from typing import Dict, List
import os


def get_string_with_indent(indent: int, string: str) -> str:
    return "\t" * indent + string


def get_stripped_string_or_none(s) -> str | None:
    return str(s).strip() if s else None


def get_int_or_none(s) -> int | None:
    return int(s) if s else None


def get_stripped_string_or_none_in_dict(d: Dict, key: str) -> str:
    return get_stripped_string_or_none(d.get(key))


def get_int_or_none_in_dict(d: Dict, key: str) -> int:
    return get_int_or_none(d.get(key))


def get_identifier_file_path(
    ssh_directory: str, server_name: str, original_identifier_file_path: str
):
    # 提取出 original_identifier_file_path 中的文件名，然后放到  ssh_directory/server_name 文件夹下
    return os.path.normpath(
        os.path.join(
            ssh_directory, server_name, original_identifier_file_path.split("/")[-1]
        )
    )


def is_none_or_empty(s: str):
    return s is None or s.strip() == ""


class SSHEndpoint:

    def __init__(self, hostname=None, port=None, comment=None, dict: Dict = None):
        self.hostname = get_stripped_string_or_none(hostname)
        self.port = get_int_or_none(port)
        self.comment = get_stripped_string_or_none(comment)
        if dict is not None:
            self.hostname = get_stripped_string_or_none_in_dict(dict, "HostName")
            self.port = get_int_or_none_in_dict(dict, "Port")
            self.comment = get_stripped_string_or_none_in_dict(dict, "Comment")

    def set_hostname(self, hostname):
        self.hostname = str(hostname).strip()

    def set_port(self, port):
        self.port = int(port)

    def set_comment(self, comment):
        self.comment = str(comment).strip()

    def __gen_comment_str(self, indent: int) -> str:
        if is_none_or_empty(self.comment):
            return ""
        return get_string_with_indent(indent, f"# {self.comment}\n")

    def __gen_hostname_str(self, indent: int) -> str:
        if is_none_or_empty(self.hostname):
            return ""
        return get_string_with_indent(indent, f"HostName {self.hostname}\n")

    def __gen_port_str(self, indent: int) -> str:
        if self.port is None:
            return ""
        return get_string_with_indent(indent, f"Port {self.port}\n")

    def to_string(self, indent: int) -> str:
        ret = (
            self.__gen_comment_str(indent)
            + self.__gen_hostname_str(indent)
            + self.__gen_port_str(indent)
        )
        return ret

    def add_comment(self, comment: str):
        self.comment = self.comment + " " + comment if self.comment else comment

    def add_config(self, key: str, value: str, comment: str) -> bool:
        if key == "HostName" or key == "Port":
            if key == "HostName":
                self.hostname = value
            else:
                self.port = int(value)
            self.add_comment(comment)
            return True
        return False


class SSHAuthentication:

    def __init__(
        self,
        ssh_directory: str = ".",
        server_name: str = ".",
        user=None,
        identity_file=None,
        comment=None,
        dict: Dict = None,
    ):
        self.ssh_directory = ssh_directory
        self.server_name = server_name
        self.user = get_stripped_string_or_none(user)
        self.original_identity_file = get_stripped_string_or_none(identity_file)
        self.comment = get_stripped_string_or_none(comment)
        if dict is not None:
            self.user = get_stripped_string_or_none_in_dict(dict, "User")
            self.original_identity_file = get_stripped_string_or_none_in_dict(
                dict, "IdentityFile"
            )
            self.comment = get_stripped_string_or_none_in_dict(dict, "Comment")

        self.identity_file = (
            get_identifier_file_path(
                ssh_directory, server_name, self.original_identity_file
            )
            if self.original_identity_file
            else None
        )

    def set_user(self, user):
        self.user = str(user).strip()

    def set_identity_file(self, identity_file):
        self.original_identity_file = str(identity_file).strip()
        self.identity_file = get_identifier_file_path(
            self.ssh_directory, self.server_name, self.original_identity_file
        )

    def set_comment(self, comment):
        self.comment = str(comment).strip()

    def __gen_comment_str(self, indent: int) -> str:
        if is_none_or_empty(self.comment):
            return ""
        return get_string_with_indent(indent, f"# {self.comment}\n")

    def __gen_user_str(self, indent: int) -> str:
        if is_none_or_empty(self.user):
            return ""
        return get_string_with_indent(indent, f"User {self.user}\n")

    def __gen_identity_file_str(self, indent: int) -> str:
        if is_none_or_empty(self.identity_file):
            return ""
        return get_string_with_indent(indent, f"IdentityFile {self.identity_file}\n")

    def to_string(self, indent: int) -> str:
        ret = (
            self.__gen_comment_str(indent)
            + self.__gen_user_str(indent)
            + self.__gen_identity_file_str(indent)
        )
        return ret

    def add_comment(self, comment: str):
        self.comment = self.comment + " " + comment if self.comment else comment

    def add_config(self, key: str, value: str, comment: str) -> bool:
        if key == "User" or key == "IdentityFile":
            if key == "User":
                self.user = value
            else:
                self.identity_file = value
                self.original_identity_file = None
            self.add_comment(comment)
            return True
        return False


class SSHExtraConfig:
    def __init__(self, key=None, value=None, comment=None, dict: Dict = None):
        self.key = get_stripped_string_or_none(key)
        self.value = get_stripped_string_or_none(value)
        self.comment = get_stripped_string_or_none(comment)
        if dict is not None:
            self.key = get_stripped_string_or_none_in_dict(dict, "Key")
            self.value = get_stripped_string_or_none_in_dict(dict, "Value")
            self.comment = get_stripped_string_or_none_in_dict(dict, "Comment")

    def set_key(self, key):
        self.key = str(key).strip()

    def set_value(self, value):
        self.value = str(value).strip()

    def set_comment(self, comment):
        self.comment = str(comment).strip()

    def __gen_comment_str(self, indent: int) -> str:
        if is_none_or_empty(self.comment):
            return ""
        return get_string_with_indent(indent, f"# {self.comment}\n")

    def __gen_extra_config_str(self, indent: int) -> str:
        if self.key is None:
            raise ValueError("SSHExtraConfig key is None")
        if self.value is None:
            raise ValueError("SSHExtraConfig value is None")
        return get_string_with_indent(indent, f"{self.key} {self.value}\n")

    def to_string(self, indent: int) -> str:
        ret = self.__gen_comment_str(indent) + self.__gen_extra_config_str(indent)
        return ret


class SSHHostConfigChoice:

    def __init__(self, ssh_mgr, dict: Dict, endpoint_id: int = 0, auth_id: int = 0):
        self.ssh_mgr = ssh_mgr
        self.dict = dict
        self.endpoint_id = endpoint_id
        self.auth_id = auth_id


class SSHHostConfig:

    def __init__(
        self,
        name: str = None,
        comment=None,
        choice: SSHHostConfigChoice = None,
    ):
        self.name = get_stripped_string_or_none(name)
        self.comment = get_stripped_string_or_none(comment)
        self.endpoint: SSHEndpoint = SSHEndpoint()
        self.authentication: SSHAuthentication = SSHAuthentication()
        self.extra_config: List[SSHExtraConfig] = []
        self.ssh_mgr = None
        if choice is not None:
            dict = choice.dict
            self.ssh_mgr = choice.ssh_mgr
            if "ServerName" in dict:
                self.name = get_stripped_string_or_none_in_dict(dict, "ServerName")
            if "Comment" in dict:
                self.comment = get_stripped_string_or_none_in_dict(dict, "Comment")
            if "Endpoint" in dict:
                endpoints = dict["Endpoint"]
                if choice.endpoint_id >= len(endpoints):
                    raise ValueError(
                        f"SSHHostConfigChoice endpoint_id out of range: {choice.endpoint_id}"
                    )
                self.endpoint = SSHEndpoint(dict=endpoints[choice.endpoint_id])
            if "Authentication" in dict:
                auths = dict["Authentication"]
                if choice.auth_id >= len(auths):
                    raise ValueError(
                        f"SSHHostConfigChoice auth_id out of range: {choice.auth_id}"
                    )
                self.authentication = SSHAuthentication(
                    choice.ssh_mgr.get_ssh_directory(),
                    self.name,
                    dict=auths[choice.auth_id],
                )
            if "ExtraConfig" in dict:
                self.extra_config = [
                    SSHExtraConfig(dict=extra_config)
                    for extra_config in dict["ExtraConfig"]
                ]

    def set_comment(self, comment: str):
        self.comment = str(comment).strip()

    def set_endpoint(self, endpoint: SSHEndpoint):
        self.endpoint = endpoint

    def set_authentication(self, authentication: SSHAuthentication):
        self.authentication = authentication

    def add_extra_config(self, extra_config: SSHExtraConfig):
        self.extra_config.append(extra_config)

    def __gen_comment_str(self, indent: int) -> str:
        if self.comment is None or len(self.comment) == 0:
            return ""
        return get_string_with_indent(indent, f"# {self.comment}\n")

    def __gen_host_config_header_str(self, indent: int) -> str:
        if self.name is None:
            raise ValueError("SSHHostConfig name is None")
        return get_string_with_indent(indent, f"Host {self.name}\n")

    def __gen_endpoint_str(self, indent: int) -> str:
        if self.endpoint is None:
            return ""
        return self.endpoint.to_string(indent + 1)

    def __gen_authentication_str(self, indent: int) -> str:
        if self.authentication is None:
            return ""
        return self.authentication.to_string(indent + 1)

    def __gen_extra_config_str(self, indent: int) -> str:
        ret = ""
        for extra_config in self.extra_config:
            ret += extra_config.to_string(indent + 1)
        return ret

    def get_ssh_identity_file(self) -> str | None:
        if self.authentication is None:
            return None
        return self.authentication.identity_file

    def get_ssh_original_identity_file(self) -> str | None:
        if (
            self.authentication is None
            or self.authentication.original_identity_file is None
        ):
            return None
        return self.ssh_mgr.get_abs_path_based_on_ssh_key_repo_config(
            self.authentication.original_identity_file
        )

    def to_string(self, indent: int) -> str:
        return (
            self.__gen_comment_str(indent)
            + self.__gen_host_config_header_str(indent)
            + self.__gen_endpoint_str(indent)
            + self.__gen_authentication_str(indent)
            + self.__gen_extra_config_str(indent)
        )

    def add_config(self, key: str, value: str, comment: str):
        if self.endpoint.add_config(key, value, comment):
            return
        if self.authentication.add_config(key, value, comment):
            return
        self.extra_config.append(SSHExtraConfig(key, value, comment))


# class SSHConfigBuilder:
#     def __init__(self):
#         self.ssh_host_configs: List[SSHHostConfig] = []

#     def add_ssh_host_config(self, ssh_host_config: SSHHostConfig):
#         self.ssh_host_configs.append(ssh_host_config)

#     def to_string(self, indent: int = 0) -> str:
#         ret = ""
#         # 用名字的字典序排序
#         self.ssh_host_configs.sort(key=lambda x: x.name)

#         # 检测重名
#         for i in range(len(self.ssh_host_configs) - 1):
#             if self.ssh_host_configs[i].name == self.ssh_host_configs[i + 1].name:
#                 raise ValueError(
#                     f"SSHConfigBuilder: Duplicate Host Config Name {self.ssh_host_configs[i].name}"
#                 )

#         for ssh_host_config in self.ssh_host_configs:
#             ret += ssh_host_config.to_string(indent)
#         return ret
