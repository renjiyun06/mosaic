import asyncio
from email.policy import default
import click
from click import option
from typing import Dict, List, Any
from rich.console import Console

from mosaic.core.client import AdminClient
from mosaic.core.enums import TransportType
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


# TODO Add config command to update node config

@node.command(cls=CustomCommand, name="tail-session")
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--session-id", type=str, required=True)
@option("--type", type=str, default="background")   # TODO support it
def tail_session(node_id: str, mesh_id: str, session_id: str, type: str):
    """tail the content of a background session"""
    try:
        asyncio.run(admin_client.tail_session(mesh_id, node_id, session_id))
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand, name="list-sessions")
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--type", type=str, default="background")   # TODO support it
def list_sessions(node_id: str, mesh_id: str, type: str):
    """list the background sessions of a mosaic mesh agent node"""
    try:
        sessions: List[Dict[str, Any]] = asyncio.run(
            admin_client.list_sessions(mesh_id, node_id)
        )
        for session in sessions:
            console.print(session["session_id"])
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
def stop(node_id: str, mesh_id: str):
    """stop a mosaic mesh node"""
    try:
        asyncio.run(admin_client.stop_node(mesh_id, node_id))
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
def chat(node_id: str, mesh_id: str):
    """chat with a mosaic mesh agent node"""
    try:
        asyncio.run(
            admin_client.chat_node(mesh_id, node_id, TransportType.SQLITE)
        )
    except Exception as e:
        console.print(e, style="red")


@node.command(cls=CustomCommand, name="chat-background-session")
@option("--node-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--session-id", type=str, required=True)
def chat_background_session(
    node_id: str,
    mesh_id: str,
    session_id: str
):
    """chat with a background session of a mosaic mesh agent node"""
    try:
        asyncio.run(
            admin_client.chat_background_session(mesh_id, node_id, session_id)
        )
    except Exception as e:
        console.print(e, style="red")