from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from ssh_manager.ssh_config.builder import SSHHostConfig
from ssh_manager.ssh_manager import SSHManager
from ssh_manager.utils import paths

console = Console()

app = typer.Typer(
    name="ssh-manager",
    no_args_is_help=True,
    help="Manage local SSH config alongside a remote key repository.",
)
local_app = typer.Typer(name="local", no_args_is_help=True, help="Inspect local ssh config")
remote_app = typer.Typer(name="remote", no_args_is_help=True, help="Inspect remote repo configs")
app.add_typer(local_app, name="local")
app.add_typer(remote_app, name="remote")


@dataclass
class CLIContext:
    config_path: Path
    manager: SSHManager
    current_configs: List[SSHHostConfig]
    remote_loaded: bool = False


def _compile_pattern(pattern: Optional[str]) -> Optional[re.Pattern[str]]:
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise typer.BadParameter(f"Invalid regex pattern: {exc}")


def _load_current_configs(manager: SSHManager) -> List[SSHHostConfig]:
    configs = manager.parse_current_ssh_config()
    configs.sort(key=lambda cfg: cfg.name or "")
    return configs


def _get_context(ctx: typer.Context) -> CLIContext:
    cli_ctx: CLIContext = ctx.obj  # type: ignore[assignment]
    if cli_ctx is None:
        typer.echo("CLI context was not initialized; this is unexpected.")
        raise typer.Exit(code=1)
    return cli_ctx


def _ensure_remote_loaded(ctx: typer.Context) -> None:
    cli_ctx = _get_context(ctx)
    if cli_ctx.remote_loaded:
        return
    try:
        cli_ctx.manager.read_ssh_key_repo_config()
    except FileNotFoundError:
        typer.echo(
            "Remote repository config not found. Run 'ssh-manager pull' to clone/sync it first.",
            err=True,
        )
        raise typer.Exit(code=2)
    except Exception as exc:  # pragma: no cover - defensive
        typer.echo(f"Failed to read remote repository config: {exc}", err=True)
        raise typer.Exit(code=1)
    cli_ctx.remote_loaded = True


def _host_config_to_dict(cfg: SSHHostConfig) -> Dict:
    return {
        "name": cfg.name,
        "comment": cfg.comment,
        "endpoint": {
            "hostname": cfg.endpoint.hostname,
            "port": cfg.endpoint.port,
            "comment": cfg.endpoint.comment,
        },
        "authentication": {
            "user": cfg.authentication.user,
            "identity_file": cfg.authentication.identity_file,
            "comment": cfg.authentication.comment,
        },
        "extra_config": [
            {
                "key": extra.key,
                "value": extra.value,
                "comment": extra.comment,
            }
            for extra in cfg.extra_config
        ],
    }


def _summarize_host(cfg: SSHHostConfig) -> str:
    parts: List[str] = []
    hostname = cfg.endpoint.hostname
    port = cfg.endpoint.port
    if hostname:
        parts.append(f"{hostname}:{port}" if port else hostname)
    if cfg.authentication.user:
        parts.append(f"user={cfg.authentication.user}")
    if cfg.authentication.identity_file:
        parts.append(f"id={cfg.authentication.identity_file}")
    return ", ".join(parts) if parts else "-"


def _filter_by_pattern(items: List[str], pattern: Optional[re.Pattern[str]]) -> List[str]:
    if pattern is None:
        return items
    return [item for item in items if pattern.search(item)]


def _filter_host_configs(
    configs: List[SSHHostConfig], pattern: Optional[re.Pattern[str]]
) -> List[SSHHostConfig]:
    if pattern is None:
        return configs
    return [cfg for cfg in configs if cfg.name and pattern.search(cfg.name)]


def _resolve_config_path(config: Optional[Path]) -> Path:
    if config is None:
        candidate = paths.DATA_ROOT / "config.json"
    else:
        candidate = Path(str(paths.expand_data_root(config)))
    candidate = candidate.expanduser()
    if not candidate.is_absolute():
        candidate = (paths.DATA_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _render_endpoint_table(endpoints: List[Dict]) -> Table:
    table = Table(show_header=True, header_style="bold")
    table.add_column("index", style="cyan", justify="right")
    table.add_column("HostName")
    table.add_column("Port")
    table.add_column("Comment")
    for idx, endpoint in enumerate(endpoints):
        table.add_row(
            str(idx),
            str(endpoint.get("HostName", "")),
            str(endpoint.get("Port", "")),
            endpoint.get("Comment", "") or "",
        )
    return table


def _render_auth_table(auths: List[Dict]) -> Table:
    table = Table(show_header=True, header_style="bold")
    table.add_column("index", style="cyan", justify="right")
    table.add_column("User")
    table.add_column("IdentityFile")
    table.add_column("Comment")
    for idx, auth in enumerate(auths):
        table.add_row(
            str(idx),
            auth.get("User", "") or "",
            auth.get("IdentityFile", "") or "",
            auth.get("Comment", "") or "",
        )
    return table


def _choose_index(
    label: str,
    options: List[Dict],
    provided: Optional[int],
    non_interactive: bool,
    config_name: str,
) -> int:
    if not options:
        typer.echo(f"Config '{config_name}' has no {label.lower()} options.", err=True)
        raise typer.Exit(code=1)
    if provided is not None:
        if provided < 0 or provided >= len(options):
            raise typer.BadParameter(
                f"{label} index out of range. Valid range: 0-{len(options) - 1}."
            )
        return provided
    if len(options) == 1:
        return 0
    if non_interactive:
        typer.echo(
            f"Multiple {label.lower()} options for '{config_name}'. "
            "Use --endpoint-id/--auth-id or run 'ssh-manager remote show' to inspect choices.",
            err=True,
        )
        raise typer.Exit(code=2)

    console.print(f"Select {label} for '{config_name}':")
    console.print(_render_endpoint_table(options) if label == "Endpoint" else _render_auth_table(options))
    selection = typer.prompt(f"Enter {label} index", default="0")
    try:
        idx = int(selection)
    except ValueError as exc:
        raise typer.BadParameter(f"{label} index must be an integer") from exc
    if idx < 0 or idx >= len(options):
        raise typer.BadParameter(
            f"{label} index out of range. Valid range: 0-{len(options) - 1}."
        )
    return idx


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to the ssh-manager config.json file (defaults to DATA_ROOT/config.json).",
        dir_okay=False,
        exists=False,
        readable=True,
    ),
    auto_pull: bool = typer.Option(
        False,
        "--auto-pull",
        help="Automatically pull remote repo if remote config is missing.",
    ),
):
    resolved = _resolve_config_path(config)
    if not resolved.exists():
        typer.echo(
            f"Config file not found at {resolved}. Provide --config or create it first.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        manager = SSHManager(str(resolved))
    except Exception as exc:  # pragma: no cover - defensive
        typer.echo(f"Failed to load config: {exc}", err=True)
        raise typer.Exit(code=2)

    try:
        current_configs = _load_current_configs(manager)
    except Exception as exc:  # pragma: no cover - defensive
        typer.echo(f"Failed to parse current ssh config: {exc}", err=True)
        raise typer.Exit(code=1)

    cli_ctx = CLIContext(
        config_path=resolved,
        manager=manager,
        current_configs=current_configs,
        remote_loaded=False,
    )

    if auto_pull:
        try:
            manager.pull_ssh_key_repo()
            manager.read_ssh_key_repo_config()
            cli_ctx.remote_loaded = True
        except Exception as exc:  # pragma: no cover - defensive
            typer.echo(f"Auto-pull failed: {exc}", err=True)
            raise typer.Exit(code=1)

    ctx.obj = cli_ctx


@local_app.command("list")
def list_local(
    ctx: typer.Context,
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Regex to search host names (re.search).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full host blocks."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for scripting."),
):
    cli_ctx = _get_context(ctx)
    regex = _compile_pattern(pattern)
    configs = _filter_host_configs(cli_ctx.current_configs, regex)

    if json_output:
        payload = [_host_config_to_dict(cfg) for cfg in configs]
        typer.echo(json.dumps(payload, indent=2))
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("index", justify="right", style="cyan")
    table.add_column("name")
    table.add_column("summary")
    for idx, cfg in enumerate(configs):
        table.add_row(str(idx), cfg.name or "", _summarize_host(cfg))
    console.print(table)

    if verbose:
        for cfg in configs:
            console.rule(cfg.name or "")
            console.print(cfg.to_string(0))


@remote_app.command("list")
def list_remote(
    ctx: typer.Context,
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Regex to search remote config names (re.search).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full remote config entries."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for scripting."),
):
    _ensure_remote_loaded(ctx)
    cli_ctx = _get_context(ctx)
    regex = _compile_pattern(pattern)
    names = sorted(cli_ctx.manager.ssh_key_repo_config.keys())
    names = _filter_by_pattern(names, regex)

    if json_output:
        data = (
            {name: cli_ctx.manager.ssh_key_repo_config[name] for name in names}
            if verbose
            else names
        )
        typer.echo(json.dumps(data, indent=2))
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("index", justify="right", style="cyan")
    table.add_column("config_name")
    for idx, name in enumerate(names):
        table.add_row(str(idx), name)
    console.print(table)

    if verbose:
        for name in names:
            console.rule(name)
            console.print(json.dumps(cli_ctx.manager.ssh_key_repo_config[name], indent=2))


@remote_app.command("show")
def show_remote(
    ctx: typer.Context,
    config_name: str = typer.Argument(..., help="Remote config name to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for scripting."),
):
    _ensure_remote_loaded(ctx)
    cli_ctx = _get_context(ctx)
    if config_name not in cli_ctx.manager.ssh_key_repo_config:
        typer.echo(
            f"Remote config '{config_name}' not found. Run 'ssh-manager remote list' to see available names.",
            err=True,
        )
        raise typer.Exit(code=1)
    config = cli_ctx.manager.ssh_key_repo_config[config_name]
    endpoints = config.get("Endpoint", [])
    auths = config.get("Authentication", [])
    extra = config.get("ExtraConfig", [])

    if json_output:
        typer.echo(json.dumps(config, indent=2))
        return

    console.print(f"Remote config: {config_name}")
    console.print(_render_endpoint_table(endpoints))
    console.print(_render_auth_table(auths))
    if extra:
        extra_table = Table(show_header=True, header_style="bold")
        extra_table.add_column("index", justify="right", style="cyan")
        extra_table.add_column("Key")
        extra_table.add_column("Value")
        extra_table.add_column("Comment")
        for idx, item in enumerate(extra):
            extra_table.add_row(
                str(idx), item.get("Key", ""), item.get("Value", ""), item.get("Comment", "") or "",
            )
        console.print(extra_table)


@app.command()
def add(
    ctx: typer.Context,
    config_name: str = typer.Argument(..., help="Remote config name to add locally."),
    endpoint_id: Optional[int] = typer.Option(
        None,
        "--endpoint-id",
        help="Endpoint index to use (see remote show).",
    ),
    auth_id: Optional[int] = typer.Option(
        None,
        "--auth-id",
        help="Authentication index to use (see remote show).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Fail instead of prompting when multiple choices exist.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing files."),
):
    _ensure_remote_loaded(ctx)
    cli_ctx = _get_context(ctx)

    existing = next((cfg for cfg in cli_ctx.current_configs if cfg.name == config_name), None)
    if existing:
        typer.echo(f"Config '{config_name}' already exists locally.", err=True)
        raise typer.Exit(code=1)

    if config_name not in cli_ctx.manager.ssh_key_repo_config:
        typer.echo(
            f"Config '{config_name}' not found in remote repo. Run 'ssh-manager remote list' to see available names.",
            err=True,
        )
        raise typer.Exit(code=1)

    config = cli_ctx.manager.ssh_key_repo_config[config_name]
    endpoints = config.get("Endpoint", [])
    auths = config.get("Authentication", [])

    selected_endpoint = _choose_index("Endpoint", endpoints, endpoint_id, non_interactive, config_name)
    selected_auth = _choose_index("Authentication", auths, auth_id, non_interactive, config_name)

    new_cfg = cli_ctx.manager.generate_ssh_config(
        server_name=config_name, endpoint_id=selected_endpoint, auth_id=selected_auth
    )

    if dry_run:
        console.print("Dry run: showing generated host block")
        console.print(new_cfg.to_string(0))
        return

    cli_ctx.manager.copy_identify_file(new_cfg)
    cli_ctx.current_configs.append(new_cfg)
    cli_ctx.current_configs.sort(key=lambda cfg: cfg.name or "")
    cli_ctx.manager.write_ssh_config(cli_ctx.current_configs, backup=True)
    typer.echo(f"Added '{config_name}' to ssh config.")


@app.command()
def remove(
    ctx: typer.Context,
    name_or_index: str = typer.Argument(..., help="Host name or index to remove."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing files."),
):
    cli_ctx = _get_context(ctx)

    target_idx = None
    for idx, cfg in enumerate(cli_ctx.current_configs):
        if cfg.name == name_or_index:
            target_idx = idx
            break

    if target_idx is None:
        try:
            idx_candidate = int(name_or_index)
            if 0 <= idx_candidate < len(cli_ctx.current_configs):
                target_idx = idx_candidate
        except ValueError:
            target_idx = None

    if target_idx is None:
        typer.echo(
            f"No host named/indexed '{name_or_index}' found in local ssh config.",
            err=True,
        )
        raise typer.Exit(code=1)

    target_cfg = cli_ctx.current_configs[target_idx]

    if not yes:
        if not typer.confirm(f"Remove '{target_cfg.name}' from ssh config?", default=False):
            typer.echo("Canceled.")
            return

    if dry_run:
        typer.echo(f"Dry run: would remove '{target_cfg.name}'.")
        return

    cli_ctx.manager.delete_identify_file(target_cfg)
    del cli_ctx.current_configs[target_idx]
    cli_ctx.manager.write_ssh_config(cli_ctx.current_configs, backup=True)
    typer.echo(f"Removed '{target_cfg.name}'.")


@app.command()
def flush(
    ctx: typer.Context,
    backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Create timestamped backup before replacing ssh config.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing files."),
):
    cli_ctx = _get_context(ctx)
    if dry_run:
        typer.echo("Dry run: would rewrite ssh config with current in-memory hosts.")
        return
    cli_ctx.manager.write_ssh_config(cli_ctx.current_configs, backup=backup)
    typer.echo("Flushed ssh config with atomic write.")


@app.command()
def pull(ctx: typer.Context):
    cli_ctx = _get_context(ctx)
    try:
        cli_ctx.manager.pull_ssh_key_repo()
        cli_ctx.manager.read_ssh_key_repo_config()
        cli_ctx.remote_loaded = True
    except Exception as exc:  # pragma: no cover - defensive
        typer.echo(f"Failed to pull remote repo: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Pulled remote ssh key repository.")


@app.command()
def check(ctx: typer.Context):
    cli_ctx = _get_context(ctx)
    ok = cli_ctx.manager.check_ssh_key_repo_config()
    if not ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
