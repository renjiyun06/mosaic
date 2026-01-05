"""Event definitions for Mosaic Event Mesh system"""

from typing import Optional, Dict, Any
from ..enum import EventType


class EventDefinition:
    """
    Event definition with description and payload schema.

    Provides metadata about event types in the Mosaic system,
    used for generating system prompts and validating event payloads.
    """

    def __init__(
        self,
        event_type: EventType,
        description: str,
        payload_schema: Optional[Dict[str, Any]] = None,
        always_show: bool = False
    ):
        """
        Initialize event definition.

        Args:
            event_type: EventType enum value
            description: Human-readable description of the event
            payload_schema: JSON Schema for payload (None for empty payload)
            always_show: Whether to always show this event in system prompts,
                        even if not subscribed. Set to True for events that
                        correspond to built-in MCP tools (e.g., node_message
                        for send_message tool).
        """
        self.event_type = event_type
        self.description = description
        self.payload_schema = payload_schema
        self.always_show = always_show


# ========== Event Definitions Registry ==========

EVENT_DEFINITIONS = {
    EventType.SESSION_START: EventDefinition(
        event_type=EventType.SESSION_START,
        description="A session has started",
        payload_schema=None,  # Empty payload
    ),

    EventType.SESSION_RESPONSE: EventDefinition(
        event_type=EventType.SESSION_RESPONSE,
        description="The assistant's response in its local session",
        payload_schema={
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "Assistant's response text"
                }
            },
            "required": ["response"]
        }
    ),

    EventType.USER_PROMPT_SUBMIT: EventDefinition(
        event_type=EventType.USER_PROMPT_SUBMIT,
        description="A user prompt is about to be submitted",
        payload_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "User input text"
                }
            },
            "required": ["prompt"]
        }
    ),

    EventType.PRE_TOOL_USE: EventDefinition(
        event_type=EventType.PRE_TOOL_USE,
        description="A tool is about to be used",
        payload_schema={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool being invoked"
                },
                "tool_input": {
                    "type": "object",
                    "description": "Input arguments for the tool"
                }
            },
            "required": ["tool_name", "tool_input"]
        }
    ),

    EventType.POST_TOOL_USE: EventDefinition(
        event_type=EventType.POST_TOOL_USE,
        description="A tool has been used",
        payload_schema={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool that was invoked"
                },
                "tool_output": {
                    "type": "object",
                    "description": "Output returned by the tool"
                }
            },
            "required": ["tool_name", "tool_output"]
        }
    ),

    EventType.SESSION_END: EventDefinition(
        event_type=EventType.SESSION_END,
        description="A session has ended",
        payload_schema=None,  # Empty payload
    ),

    EventType.NODE_MESSAGE: EventDefinition(
        event_type=EventType.NODE_MESSAGE,
        description="A node message",
        payload_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message content from another node"
                }
            },
            "required": ["message"]
        },
        always_show=True  # Always show since it has corresponding send_message MCP tool
    ),

    EventType.EVENT_BATCH: EventDefinition(
        event_type=EventType.EVENT_BATCH,
        description="A batch of events collected during a session",
        payload_schema={
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "description": "List of events in the batch",
                    "items": {"type": "object"}
                }
            },
            "required": ["events"]
        }
    ),

    EventType.SYSTEM_MESSAGE: EventDefinition(
        event_type=EventType.SYSTEM_MESSAGE,
        description="A system message",
        payload_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "System-level message content"
                }
            },
            "required": ["message"]
        },
        always_show=True  # Always show system messages as they are core infrastructure
    ),

    EventType.EMAIL_MESSAGE: EventDefinition(
        event_type=EventType.EMAIL_MESSAGE,
        description="An email message",
        payload_schema={
            "type": "object",
            "properties": {
                "current_message": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "from": {"type": "string"},
                        "text": {"type": "string"},
                        "date": {"type": "string"}
                    },
                    "required": ["subject", "from", "text", "date"],
                    "description": "Current email message"
                },
                "thread": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "from": {"type": "string"},
                            "text": {"type": "string"},
                            "date": {"type": "string"}
                        }
                    },
                    "description": "Previous emails in the thread"
                }
            },
            "required": ["current_message", "thread"]
        }
    ),

    EventType.SCHEDULER_MESSAGE: EventDefinition(
        event_type=EventType.SCHEDULER_MESSAGE,
        description="A scheduler message",
        payload_schema={
            "type": "object",
            "properties": {
                "scheduled_time": {
                    "type": "string",
                    "description": "ISO 8601 timestamp when this event was scheduled"
                },
                "message": {
                    "type": "string",
                    "description": "Optional message from scheduler"
                }
            }
        }
    ),

    EventType.REDDIT_SCRAPER_MESSAGE: EventDefinition(
        event_type=EventType.REDDIT_SCRAPER_MESSAGE,
        description="A reddit scraper message contains a scraped post",
        payload_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "url": {"type": "string"},
                "author": {"type": "string"},
                "score": {"type": "integer"},
                "num_comments": {"type": "integer"},
                "created_utc": {"type": "number"},
                "selftext": {"type": "string"}
            }
        }
    ),

    # Internal events (not published to Event Mesh, session-local only)
    EventType.TASK_COMPLETE_EVENT: EventDefinition(
        event_type=EventType.TASK_COMPLETE_EVENT,
        description="Task completion signal from agent (internal event)",
        payload_schema=None,  # Empty payload
        always_show=False  # Internal event, not shown in system prompts
    ),
}
