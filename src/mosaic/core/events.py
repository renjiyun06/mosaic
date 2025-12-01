from typing import Dict, List, Optional
from mosaic.core.models import EventDefinition

_EVENTS: Dict[str, EventDefinition] = {
    "cc.tool.pre_tool_use": EventDefinition(...),
    "cc.tool.post_tool_use": EventDefinition(...),
    "cc.prompt.user_prompt_submit": EventDefinition(...),
    "cc.agent.stop": EventDefinition(...),
    "cc.session.session_start": EventDefinition(...),
    "cc.session.session_end": EventDefinition(...),
}

def get_event_definition(name: str) -> Optional[EventDefinition]:
    return _EVENTS.get(name)

def get_event_names(pattern: str) -> List[str]:
    if pattern == "*":
        return list(_EVENTS.keys())
    if pattern.endswith("*"):
        return [name for name in _EVENTS.keys() if name.startswith(pattern[:-1])]
    return [name for name in _EVENTS.keys() if name == pattern]