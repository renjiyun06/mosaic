from typing import Dict, List, Optional

from mosaic.core.models import EventDefinition

_EVENTS: Dict[str, EventDefinition] = {
    "cc.tool.pre_tool_use": EventDefinition(
        name="cc.tool.pre_tool_use",
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
    "cc.tool.post_tool_use": EventDefinition(...),
    "cc.prompt.user_prompt_submit": EventDefinition(...),
    "cc.agent.stop": EventDefinition(...),
    "cc.session.session_start": EventDefinition(...),
    "cc.session.session_end": EventDefinition(...),
    "mosaic.node.message": EventDefinition(
        name="mosaic.node.message",
        description="A message from a node",
        payload_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
            },
            "required": ["content"],
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