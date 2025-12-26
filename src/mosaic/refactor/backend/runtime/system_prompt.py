"""System prompt generation for Claude Code sessions"""

import json
from jinja2 import Template
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.node import Node
from ..models.subscription import Subscription
from ..models.connection import Connection
from ..enums import NodeType, EventType
from ..database import engine
from ..logger import get_logger
from .event import EVENTS

logger = get_logger(__name__)


async def generate_system_prompt(
    node: Node,
    session_id: str
) -> str:
    """
    Generate system prompt for Claude Code session.

    This injects Mosaic network topology information into the Claude system prompt,
    allowing Claude to understand the event mesh structure and use MCP tools to
    communicate with other nodes.

    Args:
        node: Current node instance (contains mosaic_id and all metadata)
        session_id: Session UUID

    Returns:
        System prompt string
    """
    from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionType

    async with AsyncSessionType(engine) as db:
        # Use provided node instance (no need to query again)
        mosaic_id = node.mosaic_id

        # Get all nodes in the mosaic
        result = await db.execute(
            select(Node).where(
                Node.mosaic_id == mosaic_id,
                Node.deleted_at.is_(None)
            )
        )
        nodes = result.scalars().all()

        # Build node ID mapping for O(1) lookup (id -> node_id for display)
        node_map = {n.id: n for n in nodes}

        # Format node display names using model method
        formatted_nodes = [{"node_id": n.get_display_name()} for n in nodes]

        # Get subscriptions (uses database IDs as foreign keys)
        node_db_ids = [n.id for n in nodes]
        result = await db.execute(
            select(Subscription).where(
                Subscription.source_node_id.in_(node_db_ids),
                Subscription.target_node_id.in_(node_db_ids),
                Subscription.deleted_at.is_(None)
            )
        )
        subscriptions = result.scalars().all()

        # Build subscription pair set for O(1) lookup
        sub_pairs = {(sub.source_node_id, sub.target_node_id) for sub in subscriptions}

        # Format subscriptions (convert database IDs to node_id strings for display)
        formatted_subscriptions = []
        for sub in subscriptions:
            source_node = node_map.get(sub.source_node_id)
            target_node = node_map.get(sub.target_node_id)
            if source_node and target_node:
                formatted_subscriptions.append({
                    "source_id": source_node.node_id,
                    "target_id": target_node.node_id,
                    "event_type": sub.event_type
                })

        # Get connections (uses database IDs as foreign keys)
        result = await db.execute(
            select(Connection).where(
                Connection.source_node_id.in_(node_db_ids),
                Connection.target_node_id.in_(node_db_ids),
                Connection.deleted_at.is_(None)
            )
        )
        connections = result.scalars().all()

        # Filter out connections already covered by subscriptions (O(N) instead of O(N×M))
        filtered_connections = []
        for conn in connections:
            # Check if this connection is covered by a subscription (O(1) set lookup)
            if (conn.source_node_id, conn.target_node_id) not in sub_pairs:
                source_node = node_map.get(conn.source_node_id)
                target_node = node_map.get(conn.target_node_id)
                if source_node and target_node:
                    filtered_connections.append({
                        "source_id": source_node.node_id,
                        "target_id": target_node.node_id
                    })

        # Event types list
        event_types = list(EVENTS.keys())

    # Jinja2 template (matching old code structure)
    template = Template("""
You are now a node operating within the Mosaic Event Mesh system.

[Identity]
Node ID: {{ node_id }}

[Current Session]
Session ID: {{ session_id }}

[Nodes In Mesh]
{% for node in nodes -%}
- {{ node.node_id }}
{% endfor %}
{% if subscriptions or connections -%}
[Network Topology]
graph LR
{% for sub in subscriptions -%}
    {{ sub.source_id }} --> |{{ sub.event_type }}| {{ sub.target_id }}
{% endfor -%}
{% for connection in connections -%}
    {{ connection.source_id }} --> {{ connection.target_id }}
{% endfor -%}
{% endif %}
{% if event_types -%}
[Event Definitions]
{% for event_type in event_types -%}
{{ event_type }}:
    - description: {{ EVENTS[event_type].description() }}
{%- if EVENTS[event_type].payload_schema() %}
    - payload_schema: {{ json.dumps(EVENTS[event_type].payload_schema(), ensure_ascii=False) }}
{%- endif %}
{% if not loop.last %}
{% endif -%}
{% endfor -%}
{% endif -%}
""")

    system_prompt = template.render(
        node_id=node.node_id,
        session_id=session_id,
        nodes=formatted_nodes,
        subscriptions=formatted_subscriptions,
        connections=filtered_connections,
        EVENTS=EVENTS,
        event_types=event_types,
        json=json
    )

    logger.debug(f"Generated system prompt for session {session_id}:\n{system_prompt}")

    return system_prompt.strip()
