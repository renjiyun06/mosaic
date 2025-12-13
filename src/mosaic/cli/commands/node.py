import click
import json
import requests
from rich.console import Console
from prompt_toolkit.patch_stdout import StdoutProxy
from typing import Dict, Any, List

from mosaic.core.server import Response
from mosaic.core.type import NodeType, Node
from mosaic.utils.click import Group, Command

console = Console()

@click.group(name="node", cls=Group)
def node():
    """manage the mosaic nodes"""


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("type", type=str, required=True)
@click.option("--config", type=str, default="{}")
@click.option("--server-host", type=str, default="localhost", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def create(
    node_id: str, 
    type: str, 
    config: str,
    server_host: str, 
    server_port: int
):
    """create a new mosaic node"""
    url = f"http://{server_host}:{server_port}/nodes"
    response = requests.post(url, json={
        "node_id": node_id,
        "type": type,
        "config": json.loads(config)
    })
    if response.status_code != 200:
        console.print(
            f"Failed to create node: {response.status_code}", style="red"
        )
        return

    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(f"Node created", style="green")


@node.command(cls=Command)
@click.option("--server-host", type=str, default="localhost", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def list(server_host: str, server_port: int):
    """list all the mosaic nodes"""
    url = f"http://{server_host}:{server_port}/nodes"
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to list nodes: {response.status_code}", style="red"
        )
        return

    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    nodes: List[Node] = [Node.model_validate_json(node) for node in response.data]
    if not nodes:
        console.print("No nodes found", style="yellow")
        return

    for node in nodes:
        console.print(f"{node.node_id} - {node.type}")


@node.command(cls=Command)
def topology():
    """show the topology of the mosaic nodes"""
    pass


@node.command(cls=Command)
def delete():
    """delete a mosaic node"""
    pass


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--server-host", type=str, default="localhost", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def show(node_id: str, server_host: str, server_port: int):
    """show details of a mosaic node"""
    url = f"http://{server_host}:{server_port}/nodes/{node_id}"
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to get node {node_id}: {response.status_code}", style="red"
        )
        return

    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    node: Node = Node.model_validate_json(response.data)
    console.print(f"node id: {node.node_id}")
    console.print(f"type: {node.type}")
    console.print(
        f"config: \n{json.dumps(node.config, ensure_ascii=False, indent=2)}"
    )
    

@node.command(cls=Command)
def config():
    """configure the mosaic node"""
    pass


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--server-host", type=str, default="localhost", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def start(node_id: str, server_host: str, server_port: int):
    """start the mosaic node"""
    url = f"http://{server_host}:{server_port}/nodes/{node_id}/start"
    response = requests.post(url)
    if response.status_code != 200:
        console.print(
            f"Failed to start node {node_id}: {response.status_code}", style="red"
        )
        return
    
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(f"Node {node_id} started", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--server-host", type=str, default="localhost", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def stop(node_id: str, server_host: str, server_port: int):
    """stop the mosaic node"""
    url = f"http://{server_host}:{server_port}/nodes/{node_id}/stop"
    response = requests.post(url)
    if response.status_code != 200:
        console.print(
            f"Failed to stop node {node_id}: {response.status_code}", style="red"
        )
        return
    
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(f"Node {node_id} stopped", style="green")


@node.command(cls=Command)
def chat():
    """chat with the mosaic node"""
    pass


@node.command(cls=Command)
def program():
    """program the mosaic node"""
    pass