ssh-manager
===========

Manage local SSH configs in sync with a remote key repository. The CLI can pull a repo of key material and host definitions, generate Host blocks, and write them to ``~/.ssh/config`` with backups.

Features
--------
- Pull a remote SSH key/config repo and validate identity files.
- Generate Host blocks from repo entries and append or flush to your SSH config.
- Inspect local and remote configs with rich tables or JSON output for scripting.
- Resolve data root via ``SSH_MANAGER_DATA_ROOT`` or a ``SSH_CONFIG_DATA_ROOT`` marker file.

Installation
------------
```
pip install .
```

Preparing the data root
-----------------------
``ssh-manager`` looks for configuration under a data root. It resolves in this order:
1. The ``SSH_MANAGER_DATA_ROOT`` environment variable (recommended for deployments).
2. The first directory (working directory, its parents, or your home) containing a ``SSH_CONFIG_DATA_ROOT`` file, or any direct child containing that marker.

Create the marker in your chosen directory:
```
mkdir -p ~/ssh-manager-data
touch ~/ssh-manager-data/SSH_CONFIG_DATA_ROOT
```
Place your ``config.json`` inside that directory (or set ``SSH_MANAGER_DATA_ROOT`` to point to it).

Configuration
-------------
1. Create a manager config based on [config_example/ssh_manager_example_config.json](config_example/ssh_manager_example_config.json):
```
{
	"ssh_key_remote_repo": "git@your.git.server:org/keys.git",
	"ssh_key_local_repo": "./repos/keys",
	"ssh_dir": "~/.ssh"
}
```
2. Ensure your key repo contains a ``config.json`` shaped like [config_example/ssh_key_repo_example_config.json](config_example/ssh_key_repo_example_config.json).

Core commands
-------------
- Initialize/sync remote repo: ``ssh-manager pull``
- List local hosts: ``ssh-manager local list`` (``--pattern`` to filter, ``--json`` for scripting)
- List remote configs: ``ssh-manager remote list``
- Show a remote config: ``ssh-manager remote show <name>``
- Add a host from remote: ``ssh-manager add <name> [--endpoint-id N] [--auth-id N]``
- Remove a host: ``ssh-manager remove <name|index>``
- Rewrite ssh config from in-memory state: ``ssh-manager flush``
- Validate remote repo config: ``ssh-manager check``

Notes
-----
- Host blocks are written with a timestamped backup of the existing SSH config by default.
- Identity files are copied into ``<ssh_dir>/<host>/`` with user-only permissions.
- Use ``--dry-run`` on mutating commands to preview changes without writing.

Development
-----------
- Install dev extras: ``pip install .[dev]``
- Run static checks (if you enable them): ``ruff check`` / ``mypy``
- Run tests (if added): ``pytest``
