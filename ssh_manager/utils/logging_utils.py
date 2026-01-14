from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DEFAULT_RETENTION_DAYS = 7
_logger = logging.getLogger("ssh_manager.logging")


_now_func: Callable[[], datetime] = datetime.now


def _now() -> datetime:
    return _now_func()


class DailySymlinkFileHandler(logging.Handler):
    """File handler that rolls to a new dated file automatically at midnight.

    The handler writes to ``<stem>-YYYY-MM-DD.log`` inside the directory containing
    ``symlink_path``. Each rollover updates ``symlink_path`` to point at the newest
    daily file and prunes files older than ``retention_days``.
    """

    def __init__(
        self,
        symlink_path: Path | str,
        *,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        raw_path = Path(symlink_path).expanduser()
        if not raw_path.is_absolute():
            raw_path = Path.cwd() / raw_path
        self.symlink_path = raw_path
        self.log_dir = self.symlink_path.parent
        self.stem = self.symlink_path.stem
        self.retention_days = max(1, retention_days)
        self.encoding = encoding
        self._lock = threading.RLock()
        self._file_handler: Optional[logging.FileHandler] = None
        self._current_date: Optional[str] = None
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()

    @property
    def current_log_path(self) -> Path | None:
        if self._file_handler is None:
            return None
        return Path(self._file_handler.baseFilename)

    def setFormatter(self, fmt: logging.Formatter) -> None:  # noqa: D401
        super().setFormatter(fmt)
        if self._file_handler:
            self._file_handler.setFormatter(fmt)

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        with self._lock:
            self._rotate_if_needed()
            if not self._file_handler:
                return
            self._file_handler.emit(record)

    def close(self) -> None:  # noqa: D401
        with self._lock:
            if self._file_handler:
                self._file_handler.close()
                self._file_handler = None
        super().close()

    def _rotate_if_needed(self) -> None:
        today_label = _now().strftime("%Y-%m-%d")
        if self._current_date == today_label and self._file_handler:
            return
        if self._file_handler:
            self._file_handler.close()
        daily_file = self.log_dir / f"{self.stem}-{today_label}.log"
        self._file_handler = logging.FileHandler(daily_file, encoding=self.encoding)
        if self.formatter:
            self._file_handler.setFormatter(self.formatter)
        self._current_date = today_label
        _cleanup_old_logs(self.log_dir, self.stem, self.retention_days, daily_file)
        _update_symlink(self.symlink_path, daily_file)


def configure_daily_file_logger(
    log_path: Path | str | None,
    *,
    level: int = logging.INFO,
    fmt: str = DEFAULT_LOG_FORMAT,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    stream_to_stdout: bool = True,
) -> Path | None:
    """Configure logging with an optional daily file target and stdout streaming.

    If ``log_path`` is provided, a ``DailySymlinkFileHandler`` is installed to ensure
    the process automatically switches to a new dated file at midnight without
    restarting. Files older than ``retention_days`` are deleted after each rollover.
    """

    handlers: list[logging.Handler] = []
    daily_file: Path | None = None

    if log_path:
        file_handler = DailySymlinkFileHandler(log_path, retention_days=retention_days)
        handlers.append(file_handler)
        daily_file = file_handler.current_log_path

    if stream_to_stdout:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=handlers or None,
        force=True,
    )

    return daily_file


def _cleanup_old_logs(
    log_dir: Path, stem: str, retention_days: int, keep_file: Path
) -> None:
    if retention_days <= 0:
        return
    cutoff = _now().date() - timedelta(days=max(1, retention_days) - 1)
    prefix = f"{stem}-"
    for candidate in log_dir.glob(f"{stem}-*.log"):
        if candidate == keep_file:
            continue
        suffix = candidate.stem[len(prefix) :]
        try:
            file_date = datetime.strptime(suffix, "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            candidate.unlink(missing_ok=True)


def _update_symlink(link_path: Path, newest_log: Path) -> None:
    try:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(newest_log)
    except OSError as exc:  # pragma: no cover - filesystem edge cases
        _logger.warning(
            "Failed to update log symlink %s -> %s: %s", link_path, newest_log, exc
        )


__all__ = [
    "configure_daily_file_logger",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_RETENTION_DAYS",
    "DailySymlinkFileHandler",
]
