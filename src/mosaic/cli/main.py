import subprocess
import shutil
import click
import asyncio
from pathlib import Path
from rich.console import Console
from importlib.resources import files, as_file

import mosaic.core.repository as repository
from mosaic.cli.base import CustomGroup, CustomCommand
from mosaic.cli.commands.mesh import mesh
from mosaic.cli.commands.node import node
from mosaic.cli.commands.subscription import subscription


console = Console()

@click.group(name="mosaic", cls=CustomGroup)
def mosaic():
    """Mosaic CLI"""
    pass

@mosaic.command(cls=CustomCommand)
def init():
    """initialize the mosaic"""
    asyncio.run(repository.initialize())
    console.print("Mosaic initialized successfully", style="green")

@mosaic.command(cls=CustomCommand, hidden=True)
def reset():
    """reset the mosaic"""
    confirmed = click.confirm(
        "Are you sure you want to reset the Mosaic?", default=False
    )
    if not confirmed:
        return

    # Remove all the dirs and files in ~/.mosaic
    for path in (Path.home() / ".mosaic").glob("*"):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    
    asyncio.run(repository.initialize())
    console.print("Mosaic reset successfully", style="green")

@mosaic.command(cls=CustomCommand, name="start-mcp")
def start_mcp():
    """start the mosaic mcp server"""
    with as_file(files("mosaic.nodes.agent") / "mcp_server.py") as path:
        subprocess.run(["python", path], start_new_session=True)

mosaic.add_command(mesh)
mosaic.add_command(node)
mosaic.add_command(subscription)