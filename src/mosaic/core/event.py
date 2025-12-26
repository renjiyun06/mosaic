import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel

from mosaic.core.type import EventType

class MosaicEvent(BaseModel, ABC):
    event_id: str
    source_id: str
    target_id: str
    event_type: str
    upstream_session_id: str
    downstream_session_id: str
    payload: Dict[str, Any]
    created_at: str


    @classmethod
    @abstractmethod
    def description(self) -> str: ...


    @classmethod
    @abstractmethod
    def payload_schema(self) -> Dict[str, Any] | None: ...
    
    
    @abstractmethod
    def to_llm_message(self) -> str: ...


    @abstractmethod
    def to_batch_message(self) -> str: ...


class SessionStart(MosaicEvent):
    event_type: str = EventType.SESSION_START

    @classmethod
    def description(self) -> str:
        return "A session has started"


    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None


    def to_llm_message(self) -> str:
        return (
            f"<session_start from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\"></session_start>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<session_start></session_start>"
        )


class SessionResponse(MosaicEvent):
    event_type: str = EventType.SESSION_RESPONSE

    @classmethod
    def description(self) -> str:
        return "The assistant's response in its local session"


    @classmethod
    def payload_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "response": {"type": "string"},
            },
            "required": ["response"]
        }

    
    def to_llm_message(self) -> str:
        return (
            f"<session_response from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\">"
            f"{json.dumps(self.payload, ensure_ascii=False)}"
            f"</session_response>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<session_response>{json.dumps(self.payload, ensure_ascii=False)}"
            f"</session_response>"
        )


class UserPromptSubmit(MosaicEvent):
    event_type: str = EventType.USER_PROMPT_SUBMIT

    @classmethod
    def description(self) -> str:
        return "A user prompt is about to be submitted"


    @classmethod
    def payload_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
            },
            "required": ["prompt"],
        }


    def to_llm_message(self) -> str:
        return (
            f"<user_prompt_submit from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\">"
            f"{json.dumps(self.payload, ensure_ascii=False)}"
            f"</user_prompt_submit>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<user_prompt_submit>{json.dumps(self.payload, ensure_ascii=False)}"
            f"</user_prompt_submit>"
        )


class PreToolUse(MosaicEvent):
    event_type: str = EventType.PRE_TOOL_USE

    @classmethod
    def description(self) -> str:
        return "A tool is about to be used"


    @classmethod
    def payload_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_input": {"type": "object"},
            },
            "required": ["tool_name", "tool_input"],
        }

    
    def to_llm_message(self) -> str:
        return (
            f"<pre_tool_use from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\">"
            f"{json.dumps(self.payload, ensure_ascii=False)}"
            f"</pre_tool_use>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<pre_tool_use>{json.dumps(self.payload, ensure_ascii=False)}"
            f"</pre_tool_use>"
        )


class PostToolUse(MosaicEvent):
    event_type: str = EventType.POST_TOOL_USE

    @classmethod
    def description(self) -> str:
        return "A tool has been used"


    @classmethod
    def payload_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_output": {"type": "object"},
            },
            "required": ["tool_name", "tool_output"],
        }


    def to_llm_message(self) -> str:
        return (
            f"<post_tool_use from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\">"
            f"{json.dumps(self.payload, ensure_ascii=False)}"
            f"</post_tool_use>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<post_tool_use>{json.dumps(self.payload, ensure_ascii=False)}"
            f"</post_tool_use>"
        )


class SessionEnd(MosaicEvent):
    event_type: str = EventType.SESSION_END

    @classmethod
    def description(self) -> str:
        return "A session has ended"


    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None


    def to_llm_message(self) -> str:
        return (
            f"<session_end from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\"></session_end>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<session_end></session_end>"
        )


class NodeMessage(MosaicEvent):
    event_type: str = EventType.NODE_MESSAGE

    @classmethod
    def description(self) -> str:
        return "A node message"


    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None
     

    def to_llm_message(self) -> str:
        return (
            f"<node_message from_node=\"{self.source_id}\" "
            f"from_session=\"{self.upstream_session_id}\">"
            f"{self.payload.get('message')}"
            f"</node_message>"
        )


    def to_batch_message(self) -> str:
        return (
            f"<node_message>{self.payload.get('message')}</node_message>"
        )


class EventBatch(MosaicEvent):
    event_type: str = EventType.EVENT_BATCH

    @classmethod
    def description(self) -> str:
        return "A batch of events collected during a session"
    

    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None


    def to_llm_message(self) -> str:
        events = self.payload.get('events')
        if not events:
            return "<event_batch></event_batch>"
        else:
            mosaic_events: List[MosaicEvent] = []
            for event in events:
                event_type = event.get('event_type')
                mosaic_event: MosaicEvent = EVENTS[event_type](**event)
                mosaic_events.append(mosaic_event)
        
            from_node = mosaic_events[0].source_id
            from_session = mosaic_events[0].upstream_session_id

            messages = ""
            for mosaic_event in mosaic_events:
                batch_message = mosaic_event.to_batch_message()
                if batch_message:
                    messages += f"   {batch_message}\n"

            return (
                f"<event_batch from_node=\"{from_node}\" "
                f"from_session=\"{from_session}\">"
                f"{messages}"
                f"</event_batch>"
            )


    def to_batch_message(self) -> str:
        return None


class SystemMessage(MosaicEvent):
    event_type: str = EventType.SYSTEM_MESSAGE

    @classmethod
    def description(self) -> str:
        return "A system message"


    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None


    def to_llm_message(self) -> str:
        return f"<system_message>{self.payload.get('message')}</system_message>"
        

    def to_batch_message(self) -> str:
        return None


class EmailMessage(MosaicEvent):
    event_type: str = EventType.EMAIL_MESSAGE

    @classmethod
    def description(self) -> str:
        return "An email message"
    

    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return {
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
                    "required": ["subject", "from", "text", "date"]
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
                        },
                        "required": ["subject", "from", "text", "date"]
                    }
                }
            },
            "required": ["current_message", "thread"]
        }


    def to_llm_message(self) -> str:
        return (
            f"<email_message from_node=\"{self.source_id}\"> "
            f"{json.dumps(self.payload, ensure_ascii=False)}"
            f"</email_message>"
        )


    def to_batch_message(self) -> str:
        return None


class SchedulerMessage(MosaicEvent):
    event_type: str = EventType.SCHEDULER_MESSAGE

    @classmethod
    def description(self) -> str:
        return "A scheduler message"
    

    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None
    

    def to_llm_message(self) -> str:
        return (
            f"<scheduler_message>{self.payload.get('message')}"
            f"</scheduler_message>"
        )
    
    
    def to_batch_message(self) -> str:
        return None


class RedditScraperMessage(MosaicEvent):
    event_type: str = EventType.REDDIT_SCRAPER_MESSAGE

    @classmethod
    def description(self) -> str:
        return "A reddit scraper message contains a scraped post"
    
    
    @classmethod
    def payload_schema(self) -> Dict[str, Any] | None:
        return None
    

    def to_llm_message(self) -> str:
        return (
            f"<reddit_scraper_message>"
            f"{json.dumps(self.payload, ensure_ascii=False)}"
            f"</reddit_scraper_message>"
        )
    

    def to_batch_message(self) -> str:
        return None

    

EVENTS = {
    EventType.SESSION_START: SessionStart,
    EventType.SESSION_RESPONSE: SessionResponse,
    EventType.USER_PROMPT_SUBMIT: UserPromptSubmit,
    EventType.PRE_TOOL_USE: PreToolUse,
    EventType.POST_TOOL_USE: PostToolUse,
    EventType.SESSION_END: SessionEnd,
    EventType.NODE_MESSAGE: NodeMessage,
    EventType.EVENT_BATCH: EventBatch,
    EventType.SYSTEM_MESSAGE: SystemMessage,
    EventType.EMAIL_MESSAGE: EmailMessage,
    EventType.SCHEDULER_MESSAGE: SchedulerMessage,
    EventType.REDDIT_SCRAPER_MESSAGE: RedditScraperMessage,
}