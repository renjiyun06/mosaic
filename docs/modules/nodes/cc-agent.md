# CC Agent Node

## 概述
CC (Claude Code) Node 是 Mosaic 中最核心的智能体节点类型。

它作为一个**用户态实现**，继承自 `mosaic.core.BaseNode`，复用 Core 提供的事件通信和心跳机制。

## 架构

### 继承结构
```python
from mosaic.core import BaseNode

class CCNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.session_manager = SessionManager()
        self.hook_handler = HookHandler(self.client)

    async def process_event(self, event):
        # 核心业务逻辑：路由 -> 执行
        session = self.router.route(event)
        await session.execute(event)
```

### 核心组件

#### Hook Handler
*   **职责**: 捕获 Claude Code 的运行时 Hook。
*   **交互**: 调用 `self.client.outbox.send()` 发送事件。

#### Session Management
*   **SessionManager**: 维护所有活跃会话。
*   **Backend Session**: 运行在进程内的轻量级会话。
*   **Interactive Agent**: 外部独立的 Claude Code 进程。

#### Session Routing
*   **策略**: Mirroring, Tasking, Aggregation。
*   **实现**: 纯业务逻辑，不依赖 Core 内部实现。

#### MCP Server
*   **职责**: 为 Claude 提供工具。
*   **交互**: 调用 `self.client.outbox.send_blocking()` 发起阻塞请求。
