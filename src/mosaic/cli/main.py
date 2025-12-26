import os
import asyncio
import click
import json
from pathlib import Path
from rich.console import Console

import mosaic.core.db as db
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
    (mosaic_home / "config.json").touch()
    (mosaic_home / "config.json").write_text(json.dumps({
        "mosaic": {
            "server_host": "localhost",
            "server_port": 8000,
            "zmq_server_pull_host": "localhost",
            "zmq_server_pull_port": 5555,
            "zmq_server_pub_host": "localhost",
            "zmq_server_pub_port": 5556
        }
    }, indent=4))
    asyncio.run(db.ensure_initialized(mosaic_home / "mosaic.db"))


@mosaic.command(cls=Command)
@click.argument("mosaic_home", type=str, default=".")
def reset(mosaic_home: str):
    """reset the mosaic"""
    


@mosaic.command(cls=Command)
@click.argument("mosaic_home", type=str, default=".")
def start_server(
    mosaic_home: str
):
    """start the mosaic server"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Invalid mosaic home: {mosaic_home}", style="red")
        return

    # Check if the config is exists under the mosaic home
    config_file = mosaic_home / "config.json"
    if config_file.exists():
        config = json.loads(config_file.read_text())
        mosaic_config = config.get("mosaic", {})
        server_host = mosaic_config.get("server_host")
        server_port = mosaic_config.get("server_port")
        zmq_server_pull_host = mosaic_config.get("zmq_server_pull_host")
        zmq_server_pull_port = mosaic_config.get("zmq_server_pull_port")
        zmq_server_pub_host = mosaic_config.get("zmq_server_pub_host")
        zmq_server_pub_port = mosaic_config.get("zmq_server_pub_port")
    
    pid_file: Path = mosaic_home / "server.pid"
    if pid_file.exists():
        console.print(f"Server is already running", style="red")
        return

    pid = os.getpid()
    pid_file.write_text(str(pid))

    setup_logging(mosaic_home / "logs")
    try:
        server = MosaicServer(
            mosaic_home, 
            server_host, 
            server_port,
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
        )
        server.run()
    finally:
        pid_file.unlink(missing_ok=True)


mosaic.add_command(node)
mosaic.add_command(subscription)