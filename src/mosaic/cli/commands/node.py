import asyncio
import click
from click import option
from typing import Dict, List, Any, Optional
from rich.console import Console

from mosaic.core.client import AdminClient
from mosaic.core.enums import TransportType
from mosaic.nodes.agent.enums import SessionMode
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config

console = Console()
admin_client = AdminClient()

@click.group(name="node", cls=CustomGroup)
def node():
    """manage the mosaic mesh nodes"""


@node.command(cls=CustomCommand)
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--type", type=str, required=True)
@option("--config", "-c", multiple=True, callback=parse_config)
def create(node_id: str, mesh_id: str, type: str, config: Dict[str, str]):
    """create a new mosaic mesh node"""
    try:
        asyncio.run(admin_client.create_node(mesh_id, node_id, type, config))
        console.print(
            f"Node created", style="green"
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--config", "-c", multiple=True, callback=parse_config)
def config(node_id: str, mesh_id: str, config: Dict[str, str]):
    """update the config of a mosaic mesh node"""
    try:
        asyncio.run(admin_client.update_node_config(mesh_id, node_id, config))
        console.print(
            f"Node config updated", style="green"
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand, name="add-config")
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--config", "-c", multiple=True, callback=parse_config)
def add_config(node_id: str, mesh_id: str, config: Dict[str, str]):
    """add new configs to a mosaic mesh node"""
    try:
        asyncio.run(admin_client.add_node_config(mesh_id, node_id, config))
        console.print(
            f"Node config added", style="green"
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand, name="add-mcp-server")
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--server-name", type=str, required=True)
@option("--server-config", type=str, required=True)
def add_mcp_server(
    node_id: str, 
    mesh_id: str, 
    server_name: str, 
    server_config: str
):
    """add a new mcp server to a mosaic mesh node"""
    try:
        asyncio.run(admin_client.add_mcp_server(
            mesh_id, node_id, server_name, server_config
        ))
        console.print(
            f"MCP server added", style="green"
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand, name="list-sessions")
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--mode", type=str, required=False)
def list_sessions(node_id: str, mesh_id: str, mode: Optional[str]=None):
    """list the sessions of a mosaic mesh agent node"""
    try:
        sessions: List[Dict[str, Any]] = asyncio.run(
            admin_client.list_sessions(
                mesh_id, 
                node_id,
                SessionMode(mode) if mode else None
            )
        )
        for session in sessions:
            console.print(f"{session['session_id']} - {session['mode']}")
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--transport", type=str, default="sqlite")
def start(node_id: str, mesh_id: str, transport: str):
    """start a mosaic mesh node"""
    try:
        asyncio.run(
            admin_client.start_node(mesh_id, node_id, TransportType(transport))
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--force", is_flag=True, default=False)
def stop(node_id: str, mesh_id: str, force: bool):
    """stop a mosaic mesh node"""
    try:
        asyncio.run(admin_client.stop_node(mesh_id, node_id, force))
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def program(node_id: str, mesh_id: str):
    """program a mosaic mesh agent node"""
    try:
        asyncio.run(
            admin_client.program_node(mesh_id, node_id, TransportType.SQLITE)
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand)
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--session-id", type=str, required=False)
def chat(node_id: str, mesh_id: str, session_id: Optional[str]=None):
    """chat with a mosaic mesh agent node"""
    try:
        asyncio.run(
            admin_client.chat_node(mesh_id, node_id, session_id)
        )
    except Exception as e:
        console.print(e, style="red")