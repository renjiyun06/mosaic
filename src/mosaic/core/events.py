from typing import Dict, Optional
from mosaic.core.models import EventDefinition

_EVENTS: Dict[str, EventDefinition] = {
    "cc.tool.pre_tool_use": ...,
    "cc.tool.post_tool_use": ...,
    "cc.prompt.user_prompt_submit": ...,
    "cc.agent.stop": ...,
    "cc.session.session_start": ...,
    "cc.session.session_end": ...,
}

def get_event_definition(name: str) -> Optional[EventDefinition]:
    return _EVENTS.get(name)