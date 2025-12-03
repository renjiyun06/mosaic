import asyncio
import click
from click import option
from typing import Dict
from rich.console import Console

from mosaic.core.client import AdminClient
from mosaic.core.types import TransportType
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config

console = Console()
admin_client = AdminClient()

@click.group(name="node", cls=CustomGroup)
def node():
    """Manage the Mosaic Mesh Nodes"""


@node.command(cls=CustomCommand)
@option("--node_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--type", type=str, required=True)
@option("--config", "-c", multiple=True, callback=parse_config)
def create(node_id: str, mesh_id: str, type: str, config: Dict[str, str]):
    """Create a new Mosaic Mesh Node"""
    try:
        asyncio.run(admin_client.create_node(mesh_id, node_id, type, config))
        console.print(
            f"Node created", style="green"
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def program(node_id: str, mesh_id: str):
    """Program a Mosaic Mesh Agent Node"""
    try:
        asyncio.run(
            admin_client.program_node(mesh_id, node_id, TransportType.SQLITE)
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def chat(node_id: str, mesh_id: str):
    """Chat with a Mosaic Mesh Agent Node"""
    try:
        asyncio.run(
            admin_client.chat_node(mesh_id, node_id, TransportType.SQLITE)
        )
    except Exception as e:
        console.print(e, style="red")