import click
import asyncio
from rich.console import Console

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

    asyncio.run(repository.reset())
    console.print("Mosaic reset successfully", style="green")

mosaic.add_command(mesh)
mosaic.add_command(node)
mosaic.add_command(subscription)