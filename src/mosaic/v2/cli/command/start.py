"""Start command implementation"""

import os

import click
from rich.console import Console

from ..util import (
    get_instance_path,
    is_initialized,
    is_running,
    get_pid_file,
    load_config,
)

console = Console()


@click.command(name="start", help="Start Mosaic backend server")
@click.argument(
    "path",
    type=click.Path(),
    required=False,
)
def start(path: str = None):
    """Start Mosaic backend server

    Args:
        path: Instance directory path (default: ~/.mosaic)
    """
    # Get instance path
    instance_path = get_instance_path(path)

    # Check if initialized
    if not is_initialized(instance_path):
        console.print(
            f"[red]Error: Not initialized at {instance_path}[/red]"
        )
        console.print(
            f"[yellow]Run: mosaic init {path if path else ''}[/yellow]"
        )
        raise click.Abort()

    # Check if already running
    if is_running(instance_path):
        console.print(
            f"[red]Error: Instance already running[/red]"
        )
        console.print(f"[yellow]Location: {instance_path}[/yellow]")
        raise click.Abort()

    # Load configuration
    try:
        config = load_config(instance_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise click.Abort()

    # Get server settings from config (required, no defaults)
    try:
        host = config['server']['host']
        port = config['server']['port']
    except KeyError as e:
        console.print(
            f"[red]Error: Missing required config key: {e}[/red]"
        )
        console.print(
            f"[yellow]Please add [server] section with 'host' and 'port' to config.toml[/yellow]"
        )
        raise click.Abort()

    # Display startup info
    console.print(f"[cyan]Starting Mosaic from {instance_path}[/cyan]")
    console.print(f"[cyan]Server: http://{host}:{port}[/cyan]")
    console.print(f"[cyan]Docs: http://{host}:{port}/docs[/cyan]")
    console.print("")

    # Start server in foreground
    import uvicorn
    from mosaic.v2.backend.app import create_app

    # Create app instance with config
    app = create_app(instance_path, config)

    # Save PID (current process)
    pid_file = get_pid_file(instance_path)
    pid_file.write_text(str(os.getpid()))

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
        )
    finally:
        # Clean up PID file when server stops
        pid_file.unlink(missing_ok=True)
