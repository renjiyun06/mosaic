"""Enumeration types for backend"""
from enum import Enum


class NodeType(str, Enum):
    """Node type enumeration

    Defines the types of nodes that can be created in a Mosaic instance.
    """

    CLAUDE_CODE = "cc"
    AGGREGATOR = "aggregator"

    # Future node types (currently disabled):
    # SCHEDULER = "scheduler"
    # EMAIL = "email"
    # REDDIT_SCRAPER = "reddit_scraper"

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list

        Returns:
            List of all valid node type values
        """
        return [item.value for item in cls]

    @classmethod
    def labels(cls) -> dict[str, str]:
        """Get human-readable labels for each node type

        Returns:
            Dictionary mapping node type values to display labels
        """
        return {
            cls.CLAUDE_CODE.value: "Claude Code Agent",
            cls.AGGREGATOR.value: "Event Aggregator",
        }

    def get_label(self) -> str:
        """Get the human-readable label for this node type

        Returns:
            Display label for this node type
        """
        return self.labels().get(self.value, self.value)


class MosaicStatus(str, Enum):
    """Mosaic instance status enumeration"""

    ACTIVE = "active"
    INACTIVE = "inactive"

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list"""
        return [item.value for item in cls]


class SessionAlignment(str, Enum):
    """Session alignment strategy for node connections

    Defines how downstream node sessions are managed in relation to upstream node sessions.
    """

    MIRRORING = "mirroring"  # Session lifecycle synchronized with upstream
    TASKING = "tasking"      # One-time task, session closes after completion

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list

        Returns:
            List of all valid session alignment values
        """
        return [item.value for item in cls]

    @classmethod
    def labels(cls) -> dict[str, str]:
        """Get human-readable labels for each session alignment strategy

        Returns:
            Dictionary mapping session alignment values to display labels
        """
        return {
            cls.MIRRORING.value: "Mirroring Mode - Session lifecycle synchronized",
            cls.TASKING.value: "Tasking Mode - One-time task processing",
        }

    def get_label(self) -> str:
        """Get the human-readable label for this session alignment strategy

        Returns:
            Display label for this strategy
        """
        return self.labels().get(self.value, self.value)


class EventType(str, Enum):
    """Event types in Mosaic system

    Defines all types of events that can be emitted and subscribed to
    in the event mesh.
    """

    SESSION_START = "session_start"
    SESSION_RESPONSE = "session_response"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_END = "session_end"
    NODE_MESSAGE = "node_message"
    EVENT_BATCH = "event_batch"
    SYSTEM_MESSAGE = "system_message"
    EMAIL_MESSAGE = "email_message"
    SCHEDULER_MESSAGE = "scheduler_message"
    REDDIT_SCRAPER_MESSAGE = "reddit_scraper_message"

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list

        Returns:
            List of all valid event type values
        """
        return [item.value for item in cls]

    @classmethod
    def labels(cls) -> dict[str, str]:
        """Get human-readable labels for each event type (Chinese)

        Returns:
            Dictionary mapping event type values to display labels
        """
        return {
            cls.SESSION_START.value: "会话开始",
            cls.SESSION_RESPONSE.value: "会话响应",
            cls.USER_PROMPT_SUBMIT.value: "用户提示",
            cls.PRE_TOOL_USE.value: "工具调用前",
            cls.POST_TOOL_USE.value: "工具调用后",
            cls.SESSION_END.value: "会话结束",
            cls.NODE_MESSAGE.value: "节点消息",
            cls.EVENT_BATCH.value: "事件批次",
            cls.SYSTEM_MESSAGE.value: "系统消息",
            cls.EMAIL_MESSAGE.value: "邮件消息",
            cls.SCHEDULER_MESSAGE.value: "调度消息",
            cls.REDDIT_SCRAPER_MESSAGE.value: "Reddit 抓取",
        }

    def get_label(self) -> str:
        """Get the human-readable label for this event type

        Returns:
            Display label for this event type
        """
        return self.labels().get(self.value, self.value)


class SessionStatus(str, Enum):
    """Session status enumeration

    Defines the lifecycle states of a Claude Code session.
    """

    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list

        Returns:
            List of all valid session status values
        """
        return [item.value for item in cls]

    @classmethod
    def labels(cls) -> dict[str, str]:
        """Get human-readable labels for each session status

        Returns:
            Dictionary mapping session status values to display labels
        """
        return {
            cls.ACTIVE.value: "进行中",
            cls.CLOSED.value: "已关闭",
            cls.ARCHIVED.value: "已归档",
        }

    def get_label(self) -> str:
        """Get the human-readable label for this session status

        Returns:
            Display label for this session status
        """
        return self.labels().get(self.value, self.value)


class SessionMode(str, Enum):
    """Session mode enumeration

    Defines how a Claude Code session operates and emits events.
    """

    BACKGROUND = "background"  # Publish events to event mesh
    PROGRAM = "program"        # Node guidance mode, no events published
    CHAT = "chat"              # Interactive chat mode

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list

        Returns:
            List of all valid session mode values
        """
        return [item.value for item in cls]

    @classmethod
    def labels(cls) -> dict[str, str]:
        """Get human-readable labels for each session mode

        Returns:
            Dictionary mapping session mode values to display labels
        """
        return {
            cls.BACKGROUND.value: "后台模式",
            cls.PROGRAM.value: "程序模式",
            cls.CHAT.value: "对话模式",
        }

    @classmethod
    def descriptions(cls) -> dict[str, str]:
        """Get detailed descriptions for each session mode

        Returns:
            Dictionary mapping session mode values to descriptions
        """
        return {
            cls.BACKGROUND.value: "发布事件到事件网格",
            cls.PROGRAM.value: "用于节点指导，不对外发送事件",
            cls.CHAT.value: "交互式对话，持续会话",
        }

    def get_label(self) -> str:
        """Get the human-readable label for this session mode

        Returns:
            Display label for this session mode
        """
        return self.labels().get(self.value, self.value)

    def get_description(self) -> str:
        """Get the detailed description for this session mode

        Returns:
            Description for this session mode
        """
        return self.descriptions().get(self.value, self.value)


class ClaudeModel(str, Enum):
    """Claude model enumeration

    Defines available Claude AI models for sessions.
    """

    SONNET = "sonnet"
    OPUS = "opus"
    HAIKU = "haiku"

    @classmethod
    def values(cls) -> list[str]:
        """Get all enum values as a list

        Returns:
            List of all valid Claude model values
        """
        return [item.value for item in cls]

    @classmethod
    def labels(cls) -> dict[str, str]:
        """Get human-readable labels for each Claude model

        Returns:
            Dictionary mapping model values to display labels
        """
        return {
            cls.SONNET.value: "Sonnet (平衡性能，推荐)",
            cls.OPUS.value: "Opus (最强能力，高成本)",
            cls.HAIKU.value: "Haiku (快速响应，低成本)",
        }

    def get_label(self) -> str:
        """Get the human-readable label for this Claude model

        Returns:
            Display label for this model
        """
        return self.labels().get(self.value, self.value)
