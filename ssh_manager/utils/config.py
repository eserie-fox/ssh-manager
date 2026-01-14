import json
import os
from pathlib import Path
from typing import Any, Dict, Union

from ssh_manager.utils import paths

PathLike = Union[str, Path]


def _normalize_path(base: Path, value: PathLike) -> str:
    expanded = paths.expand_data_root(value)
    expanded = os.path.expandvars(os.path.expanduser(str(expanded)))
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = (base / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return str(candidate).replace("\\", "/")


def _expand_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_values(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_expand_values(item) for item in value]
    if isinstance(value, (str, Path)):
        expanded = paths.expand_data_root(value)
        expanded = os.path.expandvars(os.path.expanduser(str(expanded)))
        return expanded
    return value


class Config:

    def __init__(self, config_file_path: PathLike | None = None):
        self.config_path = self._resolve_config_path(config_file_path)
        self.config_abs_path = self.config_path.parent

        with open(self.config_path, "r", encoding="utf-8") as file:
            raw_config: Dict[str, Any] = json.load(file)

        self.config_data = _expand_values(raw_config)
        self.local_repo_abs_path = _normalize_path(
            self.config_abs_path, self.config_data["ssh_key_local_repo"]
        )
        self.config_data["ssh_key_local_repo"] = self.local_repo_abs_path

    def _resolve_config_path(self, config_file_path: PathLike | None) -> Path:
        if config_file_path is None:
            candidate = paths.DATA_ROOT / "config.json"
        else:
            expanded = paths.expand_data_root(config_file_path)
            candidate = Path(str(expanded))

        candidate = candidate.expanduser()
        if not candidate.is_absolute():
            candidate = (paths.DATA_ROOT / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if not candidate.is_file():
            raise FileNotFoundError(f"Config file not found at {candidate}")
        return candidate

    def to_abs_path_based_on_config(self, relevant_path: str) -> str:
        return _normalize_path(self.config_abs_path, relevant_path)

    def to_abs_path_based_on_local_repo(self, relevant_path: str) -> str:
        return _normalize_path(Path(self.local_repo_abs_path), relevant_path)

    def data(self):
        return self.config_data
