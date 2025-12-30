"""Subscription-related schemas for API input/output"""

from datetime import datetime
from pydantic import BaseModel, Field

from ..enum import EventType


# ==================== Input Schemas ====================

class CreateSubscriptionRequest(BaseModel):
    """Create subscription request"""

    connection_id: int = Field(
        ...,
        gt=0,
        description="Connection ID this subscription is based on",
        examples=[1, 42]
    )
    event_type: EventType = Field(
        ...,
        description="Type of event to subscribe to",
        examples=[EventType.SESSION_START, EventType.USER_PROMPT_SUBMIT]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Subscription description",
        examples=["Subscribe to user prompts for aggregation"]
    )


class UpdateSubscriptionRequest(BaseModel):
    """Update subscription request (only description can be updated)"""

    description: str | None = Field(
        None,
        max_length=500,
        description="New subscription description",
        examples=["Updated subscription description"]
    )


# ==================== Output Schemas ====================

class SubscriptionOut(BaseModel):
    """Subscription output schema"""

    id: int = Field(..., description="Subscription database ID")
    user_id: int = Field(..., description="Owner user ID")
    mosaic_id: int = Field(..., description="Mosaic ID this subscription belongs to")
    connection_id: int = Field(..., description="Connection ID this subscription is based on")
    source_node_id: str = Field(..., description="Source node identifier (denormalized from connection)")
    target_node_id: str = Field(..., description="Target node identifier (denormalized from connection)")
    event_type: EventType = Field(..., description="Type of event to subscribe to")
    description: str | None = Field(None, description="Subscription description")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        from_attributes = True  # Enable ORM mode
