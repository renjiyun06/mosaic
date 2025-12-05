from typing import Dict, List, Optional

from mosaic.core.models import EventDefinition

_EVENTS: Dict[str, EventDefinition] = {
    "cc.pre_tool_use": EventDefinition(
        name="cc.pre_tool_use",
        description="A tool is about to be used",
        payload_schema={
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_input": {"type": "object"},
            },
            "required": ["tool_name", "tool_input"],
        }
    ),
    "cc.user_prompt_submit": EventDefinition(
        name="cc.user_prompt_submit",
        description="A user prompt is about to be submitted",
        payload_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
            },
            "required": ["prompt"],
        }
    ),
    "dummy.dummy_event": EventDefinition(
        name="dummy.dummy_event",
        description="A dummy event",
        payload_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
            },
            "required": ["message"],
        }
    )
}

def get_event_definition(name: str) -> Optional[EventDefinition]:
    return _EVENTS.get(name)

def get_event_names(pattern: str) -> List[str]:
    if pattern == "*":
        return list(_EVENTS.keys())
    if pattern.endswith("*"):
        return [name for name in _EVENTS.keys() if name.startswith(pattern[:-1])]
    return [name for name in _EVENTS.keys() if name == pattern]