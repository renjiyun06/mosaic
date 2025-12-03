import json
import asyncio
import click
from click import option
from typing import Dict, Optional
from rich.console import Console
from rich.table import Table

from mosaic.core.client import AdminClient
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config

console = Console()
admin_client = AdminClient()

@click.group(name="sub", cls=CustomGroup)
def subscription():
    """Manage the Mosaic Mesh Subscriptions"""


@subscription.command(cls=CustomCommand, name="create")
@option("--source-id", type=str, required=True)
@option("--target-id", type=str, required=True)
@option("--event-pattern", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--session-routing-strategy", type=str, required=True)
@option(
    "--session-routing-strategy-config", 
    "-c", 
    multiple=True, 
    callback=parse_config
)
def create(
    source_id: str,
    target_id: str,
    event_pattern: str,
    mesh_id: str,
    session_routing_strategy: str,
    session_routing_strategy_config: Dict[str, str],
):
    """Create a new subscription in the mesh"""
    try:
        asyncio.run(
            admin_client.create_subscription(
                mesh_id, source_id, target_id, event_pattern, 
                session_routing_strategy, session_routing_strategy_config
            )
        )
        console.print(f"Subscription created", style="green")
    except Exception as e:
        console.print(e, style="red")


@subscription.command(cls=CustomCommand, name="list")
@option("--source-id", type=str, required=True)
@option("--target-id", type=str, required=False)
@option("--mesh-id", type=str, required=True)
def list(source_id: str, target_id: Optional[str], mesh_id: str):
    """List the subscriptions"""
    try:
        subscriptions = asyncio.run(
            admin_client.list_subscriptions(mesh_id, source_id, target_id)
        )
        table = Table(title="")
        table.add_column("Source")
        table.add_column("Target")
        table.add_column("Event Pattern")
        table.add_column("Is Blocking")
        table.add_column("Session Routing Strategy")
        table.add_column("Session Routing Strategy Config")
        for subscription in subscriptions:
            table.add_row(
                subscription.source_id, 
                subscription.target_id, 
                subscription.event_pattern, 
                "Yes" if subscription.is_blocking else "No", 
                subscription.session_routing_strategy, 
                json.dumps(subscription.session_routing_strategy_config)
            )
        console.print(table)
    except Exception as e:
        console.print(e, style="red")
    

@subscription.command(cls=CustomCommand, name="delete")
@option("--source-id", type=str, required=True)
@option("--target-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def delete(source_id: str, target_id: str, mesh_id: str):
    """Delete a subscription"""
    try:
        asyncio.run(
            admin_client.delete_subscription(mesh_id, source_id, target_id)
        )
        console.print(f"Subscription deleted", style="green")
    except Exception as e:
        console.print(e, style="red")