"""Topology API response schemas"""
from typing import Any
from pydantic import BaseModel


class TopologyNodeResponse(BaseModel):
    """Schema for topology node information"""

    id: str
    node_id: str
    type: str
    config: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class TopologyConnectionResponse(BaseModel):
    """Schema for topology connection information"""

    source_node_id: str
    target_node_id: str
    alignment: str

    model_config = {"from_attributes": True}


class TopologySubscriptionResponse(BaseModel):
    """Schema for topology subscription information"""

    source_node_id: str
    target_node_id: str
    event_type: str

    model_config = {"from_attributes": True}


class TopologyResponse(BaseModel):
    """Schema for complete topology visualization data"""

    nodes: list[TopologyNodeResponse]
    connections: list[TopologyConnectionResponse]
    subscriptions: list[TopologySubscriptionResponse]
