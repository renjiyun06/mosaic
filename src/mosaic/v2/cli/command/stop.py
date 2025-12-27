"""Stop command implementation"""

import click
from rich.console import Console

from ..util import (
    get_instance_path,
    is_initialized,
    is_running,
    get_pid_file,
)

console = Console()


@click.command(name="stop", help="Stop Mosaic backend server")
@click.argument(
    "path",
    type=click.Path(),
    required=False,
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force kill if graceful shutdown fails",
)
def stop(path: str = None, force: bool = False):
    """Stop Mosaic backend server

    Args:
        path: Instance directory path (default: ~/.mosaic)
        force: Force kill if graceful shutdown fails
    """
    # Get instance path
    instance_path = get_instance_path(path)

    # Check if initialized
    if not is_initialized(instance_path):
        console.print(
            f"[red]Error: Not initialized at {instance_path}[/red]"
        )
        raise click.Abort()

    # Check if running
    if not is_running(instance_path):
        console.print(f"[yellow]Instance not running at {instance_path}[/yellow]")
        return

    # TODO: Implement stop logic
    # 1. Send SIGTERM for graceful shutdown
    # 2. Wait up to 10 seconds
    # 3. If still running and --force, send SIGKILL
    # 4. Clean up PID file
    # 5. Display success message

    console.print(
        f"[yellow]Stop command not yet implemented[/yellow]"
    )
