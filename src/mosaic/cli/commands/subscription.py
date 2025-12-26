from email.policy import default
import click
import requests
import json
from rich.console import Console

from mosaic.utils.click import Group, Command
from mosaic.core.server import Response
from mosaic.utils.path import absolute_path

console = Console()

@click.group(name="sub", cls=Group)
def subscription():
    """manage the mosaic subscriptions"""


@subscription.command(cls=Command)
@click.argument("source-id", type=str, required=True)
@click.argument("target-id", type=str, required=True)
@click.argument("event-type", type=str, required=True)
@click.option("--config", type=str, default="{}")
@click.option("--mosaic-home", type=str, default=".")
def create(
    source_id: str, 
    target_id: str, 
    event_type: str, 
    config: str,
    mosaic_home: str
):
    """create a new mosaic subscription"""
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

    url = f"http://{server_host}:{server_port}/subscriptions"
    response = requests.post(url, json={
        "source_id": source_id,
        "target_id": target_id,
        "event_type": event_type,
        "config": json.loads(config)
    })
    if response.status_code != 200:
        console.print(
            f"Failed to create subscription: {response.status_code}", style="red"
        )
        return

    response = Response.model_validate_json(response.text)
    if not response.success:
        console.print(f"{response.message}", style="red")
        return

    console.print(f"Subscription created", style="green")


@subscription.command(cls=Command)
def delete():
    """delete a mosaic subscription"""
    pass