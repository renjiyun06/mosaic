import asyncio
import click
import json
import sys
import subprocess
from pathlib import Path
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
def start(mesh_id: str):
    """Start the Mosaic Daemon"""
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

@mosaic.command(cls=CustomCommand)
@argument("mesh_id", type=str, required=True)
def stop(mesh_id: str):
    """Stop the Mosaic Daemon"""
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

mosaic.add_command(mesh)
mosaic.add_command(node)