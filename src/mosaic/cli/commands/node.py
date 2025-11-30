import asyncio
from pathlib import Path
import click
from click import argument, option
from typing import Dict
from rich.console import Console

import mosaic.core.meta as meta
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config
from mosaic.core.models import Node
from mosaic.core.types import NodeType, TransportType
from mosaic.core.catalog import NODE_CATALOG
from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode

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


@node.command(cls=CustomCommand)
@argument("node_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def program(node_id: str, mesh_id: str):
    """Program a Mosaic Mesh Agent Node"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return
    
    node = meta.get_node(mesh_id, node_id)
    if not node:
        console.print(f"Node {node_id} not found", style="red")
        return
    
    if node.type not in [
        NodeType.CLAUDE_CODE, 
        NodeType.CODEX, 
        NodeType.GEMINI, 
        NodeType.CURSOR, 
        NodeType.OPENHANDS
    ]:
        console.print(f"Node {node_id} is not an agent node", style="red")
        return
    
    # TODO


@node.command(cls=CustomCommand)
@argument("node_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def chat(node_id: str, mesh_id: str):
    """Chat with a Mosaic Mesh Agent Node"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return
    
    node = meta.get_node(mesh_id, node_id)
    if not node:
        console.print(f"Node {node_id} not found", style="red")
        return

    socket_path = Path.home() / ".mosaic" / mesh_id / "daemon.sock"
    if not socket_path.exists():
        console.print(f"Daemon for mesh {mesh_id} is not running", style="yellow")
        return

    if node.type == NodeType.CLAUDE_CODE:
        cc = ClaudeCodeNode(node.mesh_id, node.node_id, TransportType.SQLITE, node.config)
        asyncio.run(cc.chat())
    elif node.type == NodeType.CODEX:
        pass
    elif node.type == NodeType.GEMINI:
        pass
    elif node.type == NodeType.CURSOR:
        pass
    elif node.type == NodeType.OPENHANDS:
        pass
    else:
        console.print(f"Node {node_id} is not an agent node", style="red")
        return
