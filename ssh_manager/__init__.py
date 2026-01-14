"""ssh-manager package public API."""

from ssh_manager.__about__ import __version__
from ssh_manager.ssh_manager import SSHManager

__all__ = ["SSHManager", "__version__"]
