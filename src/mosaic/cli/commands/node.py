import click
from click import argument, option
from typing import Dict
from rich.console import Console

import mosaic.core.meta as meta
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config
from mosaic.core.models import Node
from mosaic.core.types import NodeType

console = Console()

@click.group(name="node", cls=CustomGroup)
def node():
    """Manage the Mosaic Mesh Nodes"""

@node.command(cls=CustomCommand)
@argument("node_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--type", type=str, required=True)
@option("--config", "-c", multiple=True, callback=parse_config)
def create(node_id: str, mesh_id: str, type: str, config: Dict[str, str]):
    """Create a new Mosaic Mesh Node"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return

    if type not in NodeType:
        console.print(f"Invalid node type: {type}", style="red")
        return

    if meta.get_node(mesh_id, node_id):
        console.print(f"Node {node_id} already exists", style="red")
        return
    
    meta.create_node(Node(node_id=node_id, mesh_id=mesh_id, type=type, config=config))
    console.print(f"Node {node_id} created", style="green")