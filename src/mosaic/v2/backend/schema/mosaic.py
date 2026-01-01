"""Mosaic-related schemas for API input/output"""

from datetime import datetime
from pydantic import BaseModel, Field

from ..enum import MosaicStatus


# ==================== Input Schemas ====================

class CreateMosaicRequest(BaseModel):
    """Create mosaic request"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Mosaic name",
        examples=["My First Mosaic"]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Mosaic description",
        examples=["A simple event mesh for testing"]
    )


class UpdateMosaicRequest(BaseModel):
    """Update mosaic request (only name and description can be updated)"""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="New mosaic name",
        examples=["Updated Mosaic Name"]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="New mosaic description",
        examples=["Updated description"]
    )


# ==================== Output Schemas ====================

class MosaicOut(BaseModel):
    """Mosaic output schema (includes statistics and runtime status)"""

    id: int = Field(..., description="Mosaic ID")
    user_id: int = Field(..., description="Owner user ID")
    name: str = Field(..., description="Mosaic name")
    description: str | None = Field(None, description="Mosaic description")
    status: MosaicStatus = Field(..., description="Mosaic runtime status")
    node_count: int = Field(..., description="Number of nodes in this mosaic")
    active_session_count: int = Field(..., description="Number of active sessions")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        from_attributes = True  # Enable ORM mode


# ==================== Topology Schemas ====================

class TopologyNodeOut(BaseModel):
    """Simplified node data for topology visualization"""

    node_id: str = Field(..., description="Unique node identifier within mosaic")
    node_type: str = Field(..., description="Node type")
    config: dict | None = Field(None, description="Node configuration (for display purposes)")

    class Config:
        from_attributes = True


class TopologyConnectionOut(BaseModel):
    """Simplified connection data for topology visualization"""

    source_node_id: str = Field(..., description="Source node identifier")
    target_node_id: str = Field(..., description="Target node identifier")
    session_alignment: str = Field(..., description="Session alignment strategy")

    class Config:
        from_attributes = True


class TopologySubscriptionOut(BaseModel):
    """Simplified subscription data for topology visualization"""

    source_node_id: str = Field(..., description="Source node identifier")
    target_node_id: str = Field(..., description="Target node identifier")
    event_type: str = Field(..., description="Event type subscribed to")

    class Config:
        from_attributes = True


class TopologyOut(BaseModel):
    """Complete topology data for a mosaic"""

    nodes: list[TopologyNodeOut] = Field(..., description="List of nodes in the mosaic")
    connections: list[TopologyConnectionOut] = Field(..., description="List of connections between nodes")
    subscriptions: list[TopologySubscriptionOut] = Field(..., description="List of event subscriptions")

    class Config:
        from_attributes = True
