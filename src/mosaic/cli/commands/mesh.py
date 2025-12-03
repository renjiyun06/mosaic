import json
import asyncio
import click
from click import option
from rich.console import Console

from mosaic.core.client import AdminClient
from mosaic.cli.base import CustomGroup, CustomCommand

console = Console()
admin_client = AdminClient()

@click.group(name="mesh", cls=CustomGroup)
def mesh():
    """Manage the Mosaic Meshes"""


@mesh.command(cls=CustomCommand)
@option("--mesh-id", type=str, required=True)
def create(mesh_id: str):
    """Create a new Mosaic Mesh"""
    try:
        asyncio.run(admin_client.create_mesh(mesh_id))
        console.print(f"Mesh created", style="green")
    except Exception as e:
        console.print(e, style="red")


@mesh.command(cls=CustomCommand)
@option("--mesh-id", type=str, required=True)
def start(mesh_id: str):
    """Start the Mosaic Daemon"""
    try:
        asyncio.run(admin_client.start_mesh(mesh_id))
        console.print(f"Mesh {mesh_id} started", style="green")
    except Exception as e:
        console.print(e, style="red")


@mesh.command(cls=CustomCommand)
@option("--mesh-id", type=str, required=True)
def stop(mesh_id: str):
    """Stop the Mosaic Daemon"""
    try:
        asyncio.run(admin_client.stop_mesh(mesh_id))
        console.print(f"Mesh {mesh_id} stopped", style="green")
    except Exception as e:
        console.print(e, style="red")


@mesh.command(cls=CustomCommand)
@option("--mesh-id", type=str, required=True)
def status(mesh_id: str):
    """Get the status of a Mosaic Mesh"""
    try:
        status = asyncio.run(admin_client.get_mesh_status(mesh_id))
        console.print(f"Mesh {mesh_id} status: {status}", style="green")
    except Exception as e:
        console.print(e, style="red")


@mesh.command(cls=CustomCommand, name="list")
def list_mesh():
    """List all Mosaic Meshes"""
    try:
        meshes = asyncio.run(admin_client.list_meshes())
        for mesh in meshes:
            console.print(f"{mesh.mesh_id}")
    except Exception as e:
        console.print(e, style="red")


@mesh.command(cls=CustomCommand, name="list-nodes")
@option("--mesh-id", type=str, required=True)
def list_nodes(mesh_id: str):
    """List all nodes in a Mosaic Mesh"""
    try:
        nodes = asyncio.run(admin_client.list_nodes(mesh_id))
        for node in nodes:
            console.print(
                f"{node.node_id} - {node.type} - {json.dumps(node.config)}"
            )
    except Exception as e:
        console.print(e, style="red")