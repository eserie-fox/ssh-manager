#!/bin/python
import json
import re
import os
import shutil
from typing import List
from ssh_manager.ssh_config.builder import SSHHostConfig
from ssh_manager.ssh_manager import SSHManager

g = {}


def ssh_manager() -> SSHManager:
    return g["ssh_manager"]


def current_ssh_config() -> List[SSHHostConfig]:
    ret = g["current_ssh_config"]
    ret.sort(key=lambda x: x.name)
    return ret


def lls(r: str = ""):
    configs = current_ssh_config()
    for i in range(len(configs)):
        if r and len(r) > 0:
            if not re.match(r, configs[i].name):
                continue
        print(f"{i}: {configs[i].name}")
        print(configs[i].to_string(1))
        print()


def rls(r: str = ""):
    mgr = ssh_manager()
    remote_configs = mgr.ssh_key_repo_config
    for config_name in remote_configs:
        if r and len(r) > 0:
            if not re.match(r, config_name):
                continue
        config = remote_configs[config_name]
        print(json.dumps(config, indent=4))
        print()


def flush():
    configs = current_ssh_config()
    mgr = ssh_manager()
    ssh_config = mgr.get_ssh_config_path()
    shutil.move(ssh_config, ssh_config + ".bak")
    print("Backup current config to " + ssh_config + ".bak")
    for i in range(len(configs)):
        mgr.append_ssh_host_config(configs[i])
    print("Flush current config to " + ssh_config)


def lrm(id: int):
    configs = current_ssh_config()
    if id >= len(configs):
        raise ValueError(f"id out of range: {id}")
    print(f"Remove config {configs[id].name} (Y/n)?\n{configs[id].to_string(1)}")
    result = input("(Y/n):")
    if result != "Y":
        print("Canceled.")
        return
    mgr = ssh_manager()
    mgr.delete_identify_file(configs[id])
    del configs[id]
    flush()


def ladd(config_name: str, endpoint_id: int | None = None, auth_id: int | None = None):
    mgr = ssh_manager()
    if config_name not in mgr.ssh_key_repo_config:
        raise ValueError(f"config_name not in repo: {config_name}")
    local_configs = current_ssh_config()
    for i in range(len(local_configs)):
        if local_configs[i].name == config_name:
            raise ValueError(f"config_name already exists: {config_name}")

    config = mgr.ssh_key_repo_config[config_name]
    if endpoint_id is None:
        if len(config["Endpoint"]) > 1:
            raise ValueError(
                f"config_name has multiple endpoints[1]: {config_name}: {config['Endpoint']}"
            )
        else:
            endpoint_id = 0
    if auth_id is None:
        if len(config["Authentication"]) > 1:
            raise ValueError(
                f"config_name has multiple auths[2]: {config_name}: {config['Authentication']}"
            )
        else:
            auth_id = 0

    generated_ssh_config = mgr.generate_ssh_config(config_name, endpoint_id, auth_id)
    local_configs.append(generated_ssh_config)
    mgr.append_ssh_host_config(generated_ssh_config)

    flush()


def pull():
    ssh_manager().pull_ssh_key_repo()
    initialize()

def rcheck():
    ssh_manager().check_ssh_key_repo_config()

def initialize():
    g.clear()
    mgr = SSHManager("config.json")
    g["ssh_manager"] = mgr
    try:
        mgr.read_ssh_key_repo_config()
    except:
        pull()
        return
    g["current_ssh_config"] = mgr.parse_current_ssh_config()


if __name__ == "__main__":
    initialize()
    import code
    code.interact(local=locals())
