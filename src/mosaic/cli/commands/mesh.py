import click
from click import argument
from rich.console import Console
from mosaic.cli.base import CustomGroup, CustomCommand
import mosaic.core.meta as meta
from mosaic.core.models import Mesh

console = Console()

@click.group(name="mesh", cls=CustomGroup)
def mesh():
    """Manage the Mosaic Meshes"""

@mesh.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def create(mesh_id: str):
    """Create a new Mosaic Mesh"""
    if meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} already exists", style="red")
        return
    meta.create_mesh(Mesh(mesh_id=mesh_id))
    console.print(f"Mesh {mesh_id} created", style="green")

@mesh.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def start(mesh_id: str):
    """Start a Mosaic Mesh"""
    pass

@mesh.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def stop(mesh_id: str):
    """Stop a Mosaic Mesh"""
    pass

@mesh.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def status(mesh_id: str):
    """Get the status of a Mosaic Mesh"""
    mesh = meta.get_mesh(mesh_id)
    if not mesh:
        console.print(f"Mesh {mesh_id} not found", style="red")
        return
    console.print(f"{mesh.mesh_id} - {mesh.status}")

@mesh.command(cls=CustomCommand, name="list")
def list_mesh():
    """List all Mosaic Meshes"""
    for mesh in meta.list_meshes():
        console.print(f"{mesh.mesh_id} - {mesh.status}")

@mesh.command(cls=CustomCommand, name="list-nodes")
@argument("mesh_id", type=str, required=True)
def list_nodes(mesh_id: str):
    """List all nodes in a Mosaic Mesh"""
    for node in meta.list_nodes(mesh_id):
        console.print(f"{node.node_id} - {node.type} - {node.status}")