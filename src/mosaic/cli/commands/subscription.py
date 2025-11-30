import json
import click
from click import argument, option
from typing import Dict, Optional, Tuple, List
from rich.console import Console
from rich.table import Table

import mosaic.core.meta as meta
from mosaic.cli.base import CustomGroup, CustomCommand, parse_config
from mosaic.core.events import get_event_names
from mosaic.core.models import Subscription
from mosaic.core.types import SessionRoutingStrategy

console = Console()

@click.group(name="sub", cls=CustomGroup)
def subscription():
    """Manage the Mosaic Mesh Subscriptions"""

@subscription.command(cls=CustomCommand, name="create")
@argument("source_id", type=str, required=True)
@argument("target_id", type=str, required=True)
@argument("event_pattern", type=str, required=True)
@option("--mesh-id", type=str, required=True)
@option("--session-routing-strategy", type=str, required=True)
@option("--session-routing-strategy-config", "-c", multiple=True, callback=parse_config)
def create(
    source_id: str,
    target_id: str,
    event_pattern: str,
    mesh_id: str,
    session_routing_strategy: str,
    session_routing_strategy_config: Dict[str, str],
):
    """Create a new subscription in the mesh"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return

    if not meta.get_node(mesh_id, source_id):
        console.print(f"Source node {source_id} not found", style="red")
        return

    if not meta.get_node(mesh_id, target_id):
        console.print(f"Target node {target_id} not found", style="red")
        return

    all_events_to_subscribe: List[Tuple[str, bool]] = []
    event_patterns = event_pattern.split(",")
    for event_pattern in event_patterns:
        is_blocking = event_pattern.startswith("@")
        event_pattern = event_pattern if not is_blocking else event_pattern[1:]
        event_names = get_event_names(event_pattern)
        if not event_names:
            console.print(f"Invalid event pattern: {event_pattern}", style="red")
            return
        all_events_to_subscribe.extend([(event_name, is_blocking) for event_name in event_names])

    subscriptions = meta.get_subscriptions_by_source(mesh_id, source_id)
    for event_name, _ in all_events_to_subscribe:
        if any(subscription.event_pattern == event_name for subscription in subscriptions):
            console.print(f"Subscription already exists for {event_name}", style="red")
            return
        
    if session_routing_strategy not in SessionRoutingStrategy:
        console.print(f"Invalid session routing strategy: {session_routing_strategy}", style="red")
        return

    for event_name, is_blocking in all_events_to_subscribe:
        subscription = Subscription(
            mesh_id=mesh_id, 
            source_id=source_id, 
            target_id=target_id, 
            event_pattern=event_name, 
            is_blocking=is_blocking, 
            session_routing_strategy=session_routing_strategy, 
            session_routing_strategy_config=session_routing_strategy_config
        )
        meta.add_subscription(subscription)

    console.print(f"Subscription created", style="green")

@subscription.command(cls=CustomCommand, name="list")
@argument("source_id", type=str, required=True)
@argument("target_id", type=str, required=False)
@option("--mesh-id", type=str, required=True)
def list(source_id: str, target_id: Optional[str], mesh_id: str):
    """List the subscriptions"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return

    if not meta.get_node(mesh_id, source_id):
        console.print(f"Source node {source_id} not found", style="red")
        return

    if target_id and not meta.get_node(mesh_id, target_id):
        console.print(f"Target node {target_id} not found", style="red")
        return

    subscriptions = meta.get_subscriptions_by_source(mesh_id, source_id)
    if target_id:
        subscriptions = [subscription for subscription in subscriptions if subscription.target_id == target_id]

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

@subscription.command(cls=CustomCommand, name="delete")
@argument("source_id", type=str, required=True)
@argument("target_id", type=str, required=True)
@option("--mesh-id", type=str, required=True)
def delete(source_id: str, target_id: str, mesh_id: str):
    """Delete a subscription"""
    if not meta.get_mesh(mesh_id):
        console.print(f"Mesh {mesh_id} not found", style="red")
        return

    if not meta.get_node(mesh_id, source_id):
        console.print(f"Source node {source_id} not found", style="red")
        return

    if not meta.get_node(mesh_id, target_id):
        console.print(f"Target node {target_id} not found", style="red")
        return

    meta.delete_subscription(mesh_id, source_id, target_id)
    console.print(f"Subscription for {source_id} to {target_id} deleted", style="green")