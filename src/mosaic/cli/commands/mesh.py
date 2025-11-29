import json
import asyncio
import sys
import subprocess
import click
from click import argument
from pathlib import Path
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
    """Start the Mosaic Daemon"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return
    
    socket_path = Path.home() / ".mosaic" / mesh_id / "daemon.sock"
    if socket_path.exists():
        async def check_running():
            try:
                _, writer = await asyncio.open_unix_connection(str(socket_path))
                writer.close()
                await writer.wait_closed()
                return True
            except:
                return False
        
        if asyncio.run(check_running()):
            console.print(f"Daemon for mesh '{mesh_id}' is already running", style="yellow")
            return
        else:
            socket_path.unlink()

    cmd = [sys.executable, "-m", "mosaic.core.daemon", "--mesh-id", mesh_id]
    subprocess.Popen(
        cmd,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL
    )
    console.print(f"Mosaic Daemon started for mesh: [bold green]{mesh_id}[/bold green]")


@mesh.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def stop(mesh_id: str):
    """Stop the Mosaic Daemon"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return
    
    socket_path = Path.home() / ".mosaic" / mesh_id / "daemon.sock"
    
    if not socket_path.exists():
        console.print("Daemon is not running", style="yellow")
        return

    async def send_stop():
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            
            request = {"type": "stop"}
            writer.write(json.dumps(request).encode() + b'\n')
            await writer.drain()
            
            response = await reader.readline()
            data = json.loads(response.decode())
            
            if data.get("status") == "ok":
                console.print("Daemon stop signal sent", style="green")
            else:
                console.print(f"Failed to stop daemon: {data.get('error')}", style="red")
                
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            console.print(f"Error communicating with daemon: {e}", style="red")

    asyncio.run(send_stop())


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