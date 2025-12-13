from email.policy import default
import click
import requests
import json
from rich.console import Console

from mosaic.utils.click import Group, Command
from mosaic.core.server import Response

console = Console()

@click.group(name="sub", cls=Group)
def subscription():
    """manage the mosaic subscriptions"""


@subscription.command(cls=Command)
@click.argument("source-id", type=str, required=True)
@click.argument("target-id", type=str, required=True)
@click.argument("event-type", type=str, required=True)
@click.option("--config", type=str, default="{}")
@click.option("--server-host", type=str, default="localhost", show_default=True)
@click.option("--server-port", type=int, default=8000, show_default=True)
def create(
    source_id: str, 
    target_id: str, 
    event_type: str, 
    config: str,
    server_host: str, 
    server_port: int
):
    """create a new mosaic subscription"""
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