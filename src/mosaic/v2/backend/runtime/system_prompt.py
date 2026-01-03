"""System prompt generation for Claude Code sessions"""

import logging
from typing import List, Dict, Any
from jinja2 import Template
from sqlmodel import select

from ..model.node import Node
from ..model.connection import Connection
from ..model.subscription import Subscription
from .event_definition import EVENT_DEFINITIONS

logger = logging.getLogger(__name__)


async def generate_system_prompt_template(
    node: Node,
    mosaic_id: int,
    async_session_factory
) -> str:
    """
    Generate system prompt template for a node.

    This is called once during node startup and cached for all sessions.
    The returned template contains a {session_id} placeholder to be filled
    when each session is created.

    Args:
        node: Current node instance
        mosaic_id: Mosaic database ID
        async_session_factory: AsyncSession factory for database access

    Returns:
        System prompt template string with {session_id} placeholder
    """
    logger.info(f"Generating system prompt template for node {node.node_id}")

    async with async_session_factory() as db:
        # 1. Get all nodes in the mosaic
        stmt = select(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        nodes = result.scalars().all()

        # Build node ID mapping for O(1) lookup
        node_map = {n.node_id: n for n in nodes}
        node_db_ids = [n.node_id for n in nodes]

        logger.debug(f"Found {len(nodes)} nodes in mosaic")

        # 2. Get all connections
        stmt = select(Connection).where(
            Connection.mosaic_id == mosaic_id,
            Connection.source_node_id.in_(node_db_ids),
            Connection.target_node_id.in_(node_db_ids),
            Connection.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        connections = result.scalars().all()

        logger.debug(f"Found {len(connections)} connections")

        # 3. Get all subscriptions
        stmt = select(Subscription).where(
            Subscription.mosaic_id == mosaic_id,
            Subscription.source_node_id.in_(node_db_ids),
            Subscription.target_node_id.in_(node_db_ids),
            Subscription.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        subscriptions = result.scalars().all()

        logger.debug(f"Found {len(subscriptions)} subscriptions")

        # 4. Build subscription pair set for O(1) lookup
        sub_pairs = {(sub.source_node_id, sub.target_node_id) for sub in subscriptions}

        # 5. Filter event definitions: show only subscribed or always_show events
        subscribed_event_types = {sub.event_type for sub in subscriptions}
        filtered_event_definitions = {
            event_type: event_def
            for event_type, event_def in EVENT_DEFINITIONS.items()
            if event_def.always_show or event_type in subscribed_event_types
        }

        # 6. Format nodes for template
        formatted_nodes = []
        for n in nodes:
            # Add node type info for better context
            formatted_nodes.append({
                "node_id": n.node_id,
                "node_type": n.node_type.value if n.node_type else "unknown"
            })

        # 7. Format subscriptions for template (convert DB IDs to node_id strings)
        formatted_subscriptions = []
        for sub in subscriptions:
            source_node = node_map.get(sub.source_node_id)
            target_node = node_map.get(sub.target_node_id)
            if source_node and target_node:
                formatted_subscriptions.append({
                    "source_id": source_node.node_id,
                    "target_id": target_node.node_id,
                    "event_type": sub.event_type.value
                })

        # 8. Filter connections not covered by subscriptions
        filtered_connections = []
        for conn in connections:
            # Skip if covered by subscription
            if (conn.source_node_id, conn.target_node_id) not in sub_pairs:
                source_node = node_map.get(conn.source_node_id)
                target_node = node_map.get(conn.target_node_id)
                if source_node and target_node:
                    filtered_connections.append({
                        "source_id": source_node.node_id,
                        "target_id": target_node.node_id
                    })

    # 9. Render template
    template = Template(SYSTEM_PROMPT_TEMPLATE)
    prompt = template.render(
        node_id=node.node_id,
        session_id_placeholder="{session_id}",
        nodes=formatted_nodes,
        subscriptions=formatted_subscriptions,
        connections=filtered_connections,
        event_definitions=filtered_event_definitions
    )

    logger.info(
        f"System prompt template generated for node {node.node_id}, "
        f"length={len(prompt)}"
    )

    return prompt.strip()


# ========== System Prompt Template ==========

SYSTEM_PROMPT_TEMPLATE = """
You are now a node operating within the Mosaic Event Mesh system.

[Identity]
Node ID: {{ node_id }}

[Current Session]
Session ID: ###session_id###

[Nodes In Mesh]
{% for node in nodes -%}
- {{ node.node_id }} (Type: {{ node.node_type }})
{% endfor -%}

{%- if subscriptions or connections %}
[Network Topology]
graph LR
{%- for sub in subscriptions %}
{{ sub.source_id }} --> |{{ sub.event_type }}| {{ sub.target_id }}
{%- endfor -%}
{%- for conn in connections %}
{{ conn.source_id }} --> {{ conn.target_id }}
{%- endfor -%}
{%- endif %}

[Event Definitions]
{% for event_type, event_def in event_definitions.items() -%}
{{ event_type.value }}:
    - description: {{ event_def.description }}
{%- if event_def.payload_schema %}
    - payload_schema:
{%- if event_def.payload_schema.properties %}
{%- for field, schema in event_def.payload_schema.properties.items() %}
        * {{ field }} ({{ schema.type }}): {{ schema.get('description', 'N/A') }}
{%- endfor -%}
{% else %}
        (complex schema)
{% endif %}
{% else %}
    - payload_schema: {} (empty)
{% endif %}
{% endfor -%}

[Event Message Format]
All events you receive follow this structure:
{% raw %}{{
  "event_id": "unique-event-id",
  "event_type": "event_type_value",
  "source_node_id": "source-node",
  "source_session_id": "source-session-uuid",
  "payload": {{ /* event-specific data, see Event Definitions above */ }}
}}{% endraw %}
"""
