"""Shared paths helpers for config and logging."""

from __future__ import annotations

from pathlib import Path

_DATA_MARKER = "SSH_CONFIG_DATA_ROOT"
_DATA_ROOT_TOKEN = "%{DATA_ROOT}"


def _has_data_marker_file(directory: Path) -> bool:
    marker_file = directory / _DATA_MARKER
    return marker_file.is_file()


def _find_data_root() -> Path:
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
    raise RuntimeError(f"Unable to locate data root using {_DATA_MARKER}")


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
