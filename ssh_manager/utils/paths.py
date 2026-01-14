"""Shared paths helpers for config and logging."""

from __future__ import annotations

import os
from pathlib import Path

_DATA_MARKER = "SSH_CONFIG_DATA_ROOT"
_DATA_ROOT_TOKEN = "%{DATA_ROOT}"
_DATA_ROOT_ENV = "SSH_CONFIG_DATA_ROOT"


def _has_data_marker_file(directory: Path) -> bool:
    marker_file = directory / _DATA_MARKER
    return marker_file.is_file()


def _candidate_from_env() -> Path | None:
    env_value = os.getenv(_DATA_ROOT_ENV)
    if not env_value:
        return None
    expanded = Path(env_value).expanduser().resolve()
    if not expanded.exists():
        raise RuntimeError(
            f"Environment variable {_DATA_ROOT_ENV} points to a non-existent path: {expanded}"
        )
    return expanded


def _find_data_root() -> Path:
    """Locate the data root using env var or marker file.

    Resolution order:
    1. Explicit ``SSH_MANAGER_DATA_ROOT`` env var, if present.
    2. First directory (working dir or any ancestor) containing ``SSH_CONFIG_DATA_ROOT`` marker.
    3. First direct child of the above candidates containing the marker.
    4. Raise ``RuntimeError`` if nothing is found.
    """

    env_candidate = _candidate_from_env()
    if env_candidate:
        return env_candidate

    candidate = Path.cwd().resolve()
    home_candidate = Path.home().resolve()
    for ancestor in (candidate, *candidate.parents, home_candidate):
        marker = ancestor / _DATA_MARKER
        if marker.is_file():
            return ancestor
        for subdir in ancestor.iterdir():
            if not subdir.is_dir():
                continue
            if _has_data_marker_file(subdir):
                return subdir
    raise RuntimeError(
        f"Unable to locate data root using {_DATA_MARKER}; set {_DATA_ROOT_ENV} to override"
    )


data_root = _find_data_root()
DATA_ROOT = data_root


def expand_data_root(value: str | Path | None) -> str | Path | None:
    """Expand %{DATA_ROOT} placeholders in configuration inputs."""

    if value is None:
        return None

    text = str(value)
    if _DATA_ROOT_TOKEN not in text:
        return value

    expanded = text.replace(_DATA_ROOT_TOKEN, str(DATA_ROOT))
    return Path(expanded) if isinstance(value, Path) else expanded


__all__ = ["DATA_ROOT", "expand_data_root"]
