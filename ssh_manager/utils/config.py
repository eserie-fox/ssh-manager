import json
import os


class Config:

    def __init__(self, config_file_path: str):
        self.config_abs_path = os.path.abspath(os.path.dirname(config_file_path))

        with open(config_file_path, "r", encoding="utf-8") as file:
            self.config_data = json.load(file)

        self.local_repo_abs_path = os.path.abspath(
            self.config_data["ssh_key_local_repo"]
        )

    def to_abs_path_based_on_config(self, relevant_path: str) -> str:
        return os.path.normpath(os.path.join(self.config_abs_path, relevant_path))

    def to_abs_path_based_on_local_repo(self, relevant_path: str) -> str:
        return os.path.normpath(os.path.join(self.local_repo_abs_path, relevant_path))

    def data(self):
        return self.config_data
