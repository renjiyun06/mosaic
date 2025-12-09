import json
import asyncio
import click
from click import option
from typing import Dict, Optional
from collections import defaultdict
from rich.console import Console
from rich.tree import Tree

from mosaic.core.client import AdminClient
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

console = Console()
admin_client = AdminClient()

@click.group(name="sub", cls=CustomGroup)
def subscription():
    """manage the mosaic mesh subscriptions"""


@subscription.command(cls=CustomCommand, name="create")
@option("--source-id", type=str, required=True)
@option("--target-id", type=str, required=True)
@option("--event-pattern", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--session-routing-strategy", "--srs", type=str, required=False)
@option(
    "--session-routing-strategy-config", "--srs-config", 
    "-c", 
    multiple=True, 
    callback=parse_config,
    required=False
)
def create(
    source_id: str,
    target_id: str,
    event_pattern: str,
    mesh_id: str,
    session_routing_strategy: Optional[str],
    session_routing_strategy_config: Optional[Dict[str, str]],
):
    """create a new subscription"""
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
def list_subs(source_id: str, target_id: Optional[str], mesh_id: str):
    """list subscriptions"""
    try:
        subscriptions = asyncio.run(
            admin_client.list_subscriptions(mesh_id, source_id, target_id)
        )

        # Group by target_id
        grouped = defaultdict(list)
        for sub in subscriptions:
            grouped[sub.target_id].append(sub)
        
        for target_id, subs in grouped.items():
            tree = Tree(f"[bold cyan]{target_id}[/]")
            for sub in subs:
                blocking = "[red]blocking[/]" if sub.is_blocking else "[dim]non-blocking[/]"
                routing = f", routing: {sub.session_routing_strategy}" if sub.session_routing_strategy else ""
                config = f", config: {json.dumps(sub.session_routing_strategy_config, ensure_ascii=False)}" \
                    if sub.session_routing_strategy_config else ""
                tree.add(
                    f"[green]{sub.event_pattern}[/] ({blocking}{routing}{config})"
                )
            console.print(tree)
    except Exception as e:
        logger.error(f"Error listing subscriptions: {e}")
        console.print(e, style="red")
    

@subscription.command(cls=CustomCommand, name="delete")
@option("--source-id", type=str, required=True)
@option("--target-id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--event-pattern", type=str, required=False)
def delete(
    source_id: str, 
    target_id: str, 
    mesh_id: str, 
    event_pattern: Optional[str],
):
    """Delete subscription(s)"""
    try:
        asyncio.run(
            admin_client.delete_subscriptions(
                mesh_id, 
                source_id, 
                target_id, 
                event_pattern
            )
        )
        console.print(f"Subscription deleted", style="green")
    except Exception as e:
        console.print(e, style="red")