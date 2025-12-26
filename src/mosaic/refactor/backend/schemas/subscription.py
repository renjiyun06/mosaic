"""Subscription request and response schemas"""
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class SubscriptionCreateRequest(BaseModel):
    """Request model for creating a subscription

    Attributes:
        source_node_id: Source node that emits events
        target_node_id: Target node that receives events
        event_type: Type of event to subscribe to (EventType enum value)
        description: Optional description of this subscription
    """

    source_node_id: str
    target_node_id: str
    event_type: str  # Will validate against EventType enum
    description: Optional[str] = None

    @field_validator("description", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Convert empty string to None"""
        if v == "":
            return None
        return v


class SubscriptionUpdateRequest(BaseModel):
    """Request model for updating a subscription

    Note: Only description can be updated.
    source_node_id, target_node_id, and event_type cannot be changed.

    Attributes:
        description: Optional description of this subscription
    """

    description: Optional[str] = None

    @field_validator("description", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Convert empty string to None"""
        if v == "":
            return None
        return v


class SubscriptionResponse(BaseModel):
    """Response model for subscription

    Attributes:
        id: Subscription ID
        user_id: User ID who owns this subscription
        mosaic_id: Mosaic instance ID
        source_node_id: Source node that emits events
        target_node_id: Target node that receives events
        event_type: Type of event subscribed to
        description: Optional description
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: int
    user_id: int
    mosaic_id: int
    source_node_id: str
    target_node_id: str
    event_type: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
