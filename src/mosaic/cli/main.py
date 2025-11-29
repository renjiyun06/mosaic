import asyncio
import click
from click import argument
from rich.console import Console

from mosaic.cli.base import CustomGroup, CustomCommand
from mosaic.cli.commands.mesh import mesh
from mosaic.cli.commands.node import node
import mosaic.core.meta as meta
from mosaic.core.daemon import Daemon

console = Console()

@click.group(name="mosaic", cls=CustomGroup)
def mosaic():
    """Mosaic CLI"""
    pass

@mosaic.command(cls=CustomCommand)
def reset():
    """Reset the Mosaic"""
    confirmed = click.confirm("Are you sure you want to reset the Mosaic?", default=False)
    if not confirmed:
        return

    meta.reset()
    console.print("Mosaic reset successfully", style="green")

@mosaic.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def start(mesh_id: str): ...

@mosaic.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def stop(mesh_id: str): ...

mosaic.add_command(mesh)
mosaic.add_command(node)