import os
import click
from pathlib import Path
from rich.console import Console

from mosaic.core.server import MosaicServer
from mosaic.cli.commands.node import node
from mosaic.cli.commands.subscription import subscription
from mosaic.utils.click import Group, Command
from mosaic.utils.path import absolute_path
from mosaic.utils.logger import setup_logging

console = Console()

@click.group(name="mosaic", cls=Group)
def mosaic():
    """Mosaic CLI"""
    pass


@mosaic.command(cls=Command)
@click.argument("mosaic_home", type=str, default=".")
def init(mosaic_home: str):
    """initialize the mosaic"""
    mosaic_home = absolute_path(mosaic_home)
    if mosaic_home.exists() and any(mosaic_home.iterdir()):
        console.print(f"Directory is not empty: {mosaic_home}", style="red")
        return

    mosaic_home.mkdir(parents=True, exist_ok=True)
    (mosaic_home / "logs").mkdir(parents=True, exist_ok=True)
    (mosaic_home / "nodes").mkdir(parents=True, exist_ok=True)
    (mosaic_home / "MOSAIC").touch()


@mosaic.command(cls=Command)
@click.argument("mosaic_home", type=str, default=".")
def reset(mosaic_home: str):
    """reset the mosaic"""
    


@mosaic.command(cls=Command)
@click.argument("mosaic_home", type=str, default=".")
@click.option("--server-host", type=str, default="0.0.0.0", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def start_server(mosaic_home: str, server_host: str, server_port: int):
    """start the mosaic server"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Invalid mosaic home: {mosaic_home}", style="red")
        return
    
    pid_file: Path = mosaic_home / "server.pid"
    if pid_file.exists():
        console.print(f"Server is already running", style="red")
        return

    pid = os.getpid()
    pid_file.write_text(str(pid))

    setup_logging(mosaic_home / "logs")
    try:
        server = MosaicServer(server_host, server_port)
        server.run()
    finally:
        pid_file.unlink(missing_ok=True)


mosaic.add_command(node)
mosaic.add_command(subscription)