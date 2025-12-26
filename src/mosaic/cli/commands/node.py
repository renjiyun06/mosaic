import asyncio
import click
import json
import requests
from rich.console import Console
from rich.markup import escape
from prompt_toolkit.patch_stdout import StdoutProxy
from typing import Dict, Any, List
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from mosaic.core.server import Response
from mosaic.core.type import NodeType, Node, Subscription, Session, Connection
from mosaic.core.zmq import ZmqClient
from mosaic.utils.click import Group, Command
from mosaic.utils.path import absolute_path

console = Console()

@click.group(name="node", cls=Group)
def node():
    """manage the mosaic nodes"""


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("type", type=str, required=True)
@click.option("--config", type=str, default="{}")
@click.option("--mosaic-home", type=str, default=".")
def create(
    node_id: str, 
    type: str, 
    config: str,
    mosaic_home: str
):
    """create a new mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    mosaic_config = json.loads(config_file.read_text()).get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

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
@click.option("--mosaic-home", type=str, default=".")
def list(mosaic_home: str):
    """list all the mosaic nodes"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

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

    nodes: List[Node] = [Node.model_validate_json(node) 
                                    for node in response.data]
    if not nodes:
        console.print("No nodes found", style="yellow")
        return

    for node in nodes:
        console.print(f"{node.node_id} - {node.type}")


@node.command(cls=Command)
@click.option("--mosaic-home", type=str, default=".")
def topology(mosaic_home: str):
    """show the topology of the mosaic nodes"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    # Get nodes
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
    nodes: List[Node] = [Node.model_validate_json(node) 
                                    for node in response.data]

    # Get connections
    url = f"http://{server_host}:{server_port}/connections"
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to list connections: {response.status_code}", style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    connections: List[Connection] = \
        [Connection.model_validate_json(connection) 
                            for connection in response.data]
    
    # Get subscriptions
    url = f"http://{server_host}:{server_port}/subscriptions"
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to list subscriptions: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    subscriptions: List[Subscription] = \
        [Subscription.model_validate_json(subscription)
            for subscription in response.data]
    

    if not nodes:
        console.print("No nodes found", style="yellow")
        return

    for node in nodes:
        if node.type == NodeType.EMAIL:
            node.node_id = f'{node.node_id}["{node.config.get("account")}"]'
        elif node.type == NodeType.SCHEDULER:
            node.node_id = f'{node.node_id}["{node.config.get("cron")}"]'

    console.print("graph LR")
    for node in nodes:
        console.print(f"{node.node_id}")
    for connection in connections:
        source_id = connection.source_id
        target_id = connection.target_id
        # Check if has subscription between source and target
        if not any(
            subscription.source_id == source_id and \
                subscription.target_id == target_id 
                for subscription in subscriptions
        ):
            console.print(
                f"{source_id} --> {target_id}"
            )
    for subscription in subscriptions:
        console.print(
            f"{subscription.source_id} --> "
            f"|{subscription.event_type}| {subscription.target_id}")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def delete(node_id: str, mosaic_home: str):
    """delete a mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}"
    response = requests.delete(url)
    if response.status_code != 200:
        console.print(
            f"Failed to delete node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    console.print(f"Node {node_id} deleted", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def show(node_id: str, mosaic_home: str):
    """show details of a mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

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
@click.argument("node-id", type=str, required=True)
@click.option("--config", type=str, default="{}")
@click.option("--mosaic-home", type=str, default=".")
def update(
    node_id: str,
    config: str,
    mosaic_home: str
):
    """configure the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    mosaic_config = json.loads(config_file.read_text()).get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}"
    response = requests.put(
        url, json={"node_id": node_id, "config": json.loads(config)}
    )
    if response.status_code != 200:
        console.print(
            f"Failed to update node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    
    console.print(f"Node {node_id} updated", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("config", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def add_config(
    node_id: str, 
    config: str, 
    mosaic_home: str
):
    """add a config to the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    mosaic_config = json.loads(config_file.read_text()).get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

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
    node.config.update(json.loads(config))
    response = requests.put(url, json={"node_id": node_id, "config": node.config})
    if response.status_code != 200:
        console.print(
            f"Failed to update node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    console.print(f"Config {config} added to node {node_id}", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("model", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def set_model(node_id: str, model: str, mosaic_home: str):
    """set the model of the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}"
    # Get the node
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
    if node.type != NodeType.CLAUDE_CODE:
        console.print(
            f"Node {node_id} does not support model setting", 
            style="red"
        )
        return
    node.config["model"] = model
    response = requests.put(
        url, json={"node_id": node_id, "config": node.config}
    )
    if response.status_code != 200:
        console.print(
            f"Failed to update node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    console.print(f"Model {model} set for node {node_id}", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("mcp-server-name", type=str, required=True)
@click.argument("mcp-server-config", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def add_mcp_server(
    node_id: str,
    mcp_server_name: str,
    mcp_server_config: str,
    mosaic_home: str
):
    """add a mcp server to the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}"
    # Get the node
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to get node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    node: Node = Node.model_validate_json(response.data)
    if node.type != NodeType.CLAUDE_CODE:
        console.print(
            f"Node {node_id} does not support MCP servers", style="red"
        )

    existing_mcp_servers = node.config.get("mcp_servers", {})
    existing_mcp_servers[mcp_server_name] = json.loads(mcp_server_config)
    node.config["mcp_servers"] = existing_mcp_servers
    response = requests.put(
        url, json={"node_id": node_id, "config": node.config}
    )
    if response.status_code != 200:
        console.print(
            f"Failed to update node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    console.print(
        f"MCP server {mcp_server_name} added to node {node_id}", style="green"
    )


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("mcp-server-name", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def remove_mcp_server(
    node_id: str,
    mcp_server_name: str,
    mosaic_home: str
):
    """remove a mcp server from the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}"
    # Get the node
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to get node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    node: Node = Node.model_validate_json(response.data)
    if node.type != NodeType.CLAUDE_CODE:
        console.print(
            f"Node {node_id} does not support MCP servers", style="red"
        )
        return
    existing_mcp_servers = node.config.get("mcp_servers", {})
    if mcp_server_name not in existing_mcp_servers:
        console.print(
            f"MCP server {mcp_server_name} not found in node {node_id}", 
            style="red"
        )
        return
    existing_mcp_servers.pop(mcp_server_name)
    node.config["mcp_servers"] = existing_mcp_servers
    response = requests.put(
        url, json={"node_id": node_id, "config": node.config}
    )
    if response.status_code != 200:
        console.print(
            f"Failed to update node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    console.print(
        f"MCP server {mcp_server_name} removed from node {node_id}", 
        style="green"
    )


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def start(node_id: str, mosaic_home: str):
    """start the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")
    
    url = f"http://{server_host}:{server_port}/nodes/{node_id}/start"
    response = requests.post(url)
    if response.status_code != 200:
        console.print(
            f"Failed to start node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(f"Node {node_id} started", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def stop(node_id: str, mosaic_home: str):
    """stop the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

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
@click.argument("node-id", type=str, required=False)
@click.option("--mosaic-home", type=str, default=".")
def restart(node_id: str, mosaic_home: str):
    """restart the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    if node_id:
        url = f"http://{server_host}:{server_port}/nodes/{node_id}/restart"
        response = requests.post(url)
        if response.status_code != 200:
            console.print(
                f"Failed to restart node {node_id}: {response.status_code}", style="red"
            )
            return
        response = Response.model_validate_json(response.text)
        if not response.success:
            console.print(f"{response.message}", style="red")
            return
        console.print(f"Node {node_id} restarted", style="green")
    else:
        url = f"http://{server_host}:{server_port}/nodes/restart"
        response = requests.post(url)
        if response.status_code != 200:
            console.print(
                f"Failed to restart all nodes: {response.status_code}", style="red"
            )
            return
        response = Response.model_validate_json(response.text)
        if not response.success:
            console.print(f"{response.message}", style="red")
            return
        console.print(f"All nodes restarted", style="green")


async def _interactive_loop(session: Session):
    async def process_message(message: Dict[str, Any]):
        type = message.get("type")
        sub_type = message.get("sub_type")
        if type == "session_message":
            if sub_type == "user_message":
                console.print(
                    f"> [bold white on grey23]"
                    f"{escape(message.get('message'))}"
                    f"[/bold white on grey23]"
                )
            elif sub_type == "assistant_text":
                console.print(f"• {message.get("message")}", markup=False)
            elif sub_type == "assistant_thinking":
                console.print(
                    f"[dim italic]<thinking>\n"
                    f"{escape(message.get('message'))}\n"
                    f"[/thinking>[/dim italic]"
                )
            elif sub_type == "assistant_tool_use":
                console.print(
                    f"[bold cyan]<tool_use>\n"
                    f"{escape(message.get('tool_name'))}\n"
                    f"{escape(json.dumps(
                        message.get('tool_input'), ensure_ascii=False
                    ))}\n"
                    f"[/tool_use>[/bold cyan]"
                )
            elif sub_type == "assistant_result":
                console.print(
                    f"\n[bold green]"
                    f"Total cost: {message.get("total_cost_usd", 0.0)} USD\n"
                    f"Total input tokens: {message.get("total_input_tokens", 0)}\n"
                    f"Total output tokens: {message.get("total_output_tokens", 0)}\n"
                    f"Usage: \n"
                    f"{json.dumps(
                        message.get("usage", {}), 
                        ensure_ascii=False, 
                        indent=2
                    )}\n"
                    f"[/bold green]"
                )
            elif sub_type == "system_message":
                console.print(f"[dim]{message.get("message")}[/dim]")

    zmq_client = ZmqClient(
        session.pull_host, 
        session.pull_port, 
        session.pub_host, 
        session.pub_port,
        subscribe_topic=f"{session.session_id}#outgoing",
        on_event=process_message
    )
    zmq_client.connect()
    
    console = Console(file=StdoutProxy(raw=True), force_terminal=True)

    bindings = KeyBindings()
    @bindings.add('c-d')
    def submit_handler(event):
        event.current_buffer.validate_and_handle()

    @bindings.add('escape')
    async def esc_handler(event):
        await zmq_client.send(
            topic=f"{session.session_id}#incoming",
            event={
                "type": "user_interrupt",
            }
        )

    prompt_session = PromptSession(
        multiline=True,
        key_bindings=bindings,
        erase_when_done=True
    )
    with patch_stdout():
        while True:
            try:
                user_input = await prompt_session.prompt_async("> ")
                await zmq_client.send(
                    topic=f"{session.session_id}#incoming",
                    event={
                        "type": "user_message",
                        "message": user_input
                    }
                )
            except (asyncio.CancelledError, KeyboardInterrupt):
                break

    zmq_client.disconnect()


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--session-id", type=str, required=False)
@click.option("--mosaic-home", type=str, default=".")
def chat(
    node_id: str, 
    session_id: str, 
    mosaic_home: str
):
    """chat with the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    session: Session = None
    if session_id:
        url = f"http://{server_host}:{server_port}/nodes/{node_id}/sessions/{session_id}"
        response = requests.get(url)
        if response.status_code != 200:
            console.print(
                f"Failed to get session {session_id}: {response.status_code}", 
                style="red"
            )
            return
        response = Response.model_validate_json(response.text)
        if not response.success:
            console.print(f"{response.message}", style="red")
            return
        session = Session.model_validate_json(response.data)
    else:
        url = f"http://{server_host}:{server_port}/nodes/{node_id}/sessions"
        response = requests.post(url, json={"mode": "chat"})
        if response.status_code != 200:
            console.print(
                f"Failed to create session: {response.status_code}", style="red"
            )
            return
        response = Response.model_validate_json(response.text)
        if not response.success:
            console.print(f"{response.message}", style="red")
            return
        session = Session.model_validate_json(response.data)

    
    asyncio.run(_interactive_loop(session))
    if not session_id:
        url = f"http://{server_host}:{server_port}/nodes/{node_id}/sessions/{session.session_id}"
        response = requests.delete(url)
        if response.status_code != 200:
            console.print(
                f"Failed to close session {session.session_id}: {response.status_code}", style="red"
            )
            return
        console.print(f"Session {session.session_id} closed", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def program(
    node_id: str,
    mosaic_home: str
):
    """program the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}/sessions"
    response = requests.post(url, json={"mode": "program"})
    if response.status_code != 200:
        console.print(
            f"Failed to create session: {response.status_code}", style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    session = Session.model_validate_json(response.data)

    asyncio.run(_interactive_loop(session))
    url = (
        f"http://{server_host}:{server_port}/nodes/{node_id}/"
        f"sessions/{session.session_id}"
    )
    response = requests.delete(url)
    if response.status_code != 200:
        console.print(
            f"Failed to close session {session.session_id}: {response.status_code}", style="red"
        )
        return
    console.print(f"Session {session.session_id} closed", style="green")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def list_sessions(node_id: str, mosaic_home: str):
    """list all the sessions of a mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}/sessions"
    response = requests.get(url)
    if response.status_code != 200:
        console.print(
            f"Failed to list sessions of node {node_id}: {response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    sessions: List[Session] = \
        [Session.model_validate_json(session) for session in response.data]
    for session in sessions:
        console.print(f"{session.session_id} - {json.dumps(session.config, ensure_ascii=False)}")


@node.command(cls=Command)
@click.argument("node-id", type=str, required=True)
@click.argument("event", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def send_event(node_id: str, event: str, mosaic_home: str):
    """send an event to the mosaic node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = f"http://{server_host}:{server_port}/nodes/{node_id}/events"
    response = requests.post(url, json=json.loads(event))
    if response.status_code != 200:
        console.print(
            f"Failed to send event to node {node_id}: {response.status_code}", style="red"
        )
        return

    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(f"Event sent to node {node_id}", style="green")


@node.command(cls=Command)
@click.argument("source-id", type=str, required=True)
@click.argument("target-id", type=str, required=True)
@click.argument("session-alignment", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def connect(
    source_id: str,
    target_id: str,
    session_alignment: str,
    mosaic_home: str
):
    """connect source node to target node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = (
        f"http://{server_host}:{server_port}"
        f"/connections/{source_id}/{target_id}"
    )
    response = requests.post(url, json={"session_alignment": session_alignment})
    if response.status_code != 200:
        console.print(
            f"Failed to connect source node to target node: "
            f"{response.status_code}", 
            style="red"
        )
        return

    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(
        f"Source node {source_id} connected to target node {target_id}", 
        style="green"
    )


@node.command(cls=Command)
@click.argument("source-id", type=str, required=True)
@click.argument("target-id", type=str, required=True)
@click.option("--mosaic-home", type=str, default=".")
def disconnect(
    source_id: str, target_id: str, mosaic_home: str
):
    """disconnect source node from target node"""
    mosaic_home = absolute_path(mosaic_home)
    mosaic_flag_file = mosaic_home / "MOSAIC"
    if not mosaic_flag_file.exists():
        console.print(f"Mosaic home is not initialized: {mosaic_home}", style="red")
        return
    config_file = mosaic_home / "config.json"
    if not config_file.exists():
        console.print(f"Config file not found: {config_file}", style="red")
        return
    config = json.loads(config_file.read_text())
    mosaic_config = config.get("mosaic", {})
    server_host = mosaic_config.get("server_host")
    server_port = mosaic_config.get("server_port")

    url = (
        f"http://{server_host}:{server_port}"
        f"/connections/{source_id}/{target_id}"
    )
    response = requests.delete(url)
    if response.status_code != 200:
        console.print(
            f"Failed to disconnect source node from target node: "
            f"{response.status_code}", 
            style="red"
        )
        return
    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return
    console.print(
        f"Source node {source_id} disconnected from "
        f"target node {target_id}", style="green"
    )