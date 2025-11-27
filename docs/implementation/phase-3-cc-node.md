# Phase 3: CC Agent Node

## 目标
在 Core 提供的基类之上，实现复杂的智能体业务逻辑。

## 任务清单

### 1. 节点实现 (mosaic.nodes.cc)
- [ ] 继承 `BaseNode` 实现 `CCNode`。
- [ ] 实现 `SessionManager`: 管理 Backend Session 生命周期。
- [ ] 实现 `SessionRouter`: 策略模式 (Mirroring, Tasking)。

### 2. 业务逻辑
- [ ] 实现 `HookHandler`: 将 Hook 转换为 Event 并发送。
- [ ] 实现 `process_event`: 将接收到的 Event 路由给 Session。

### 3. MCP 集成
- [ ] 实现 `MCPServer`: 为 Claude 提供 `respond_to_blocking` 等工具。

## 验收标准
*   CC 节点能够正确处理 `session_trace`，实现会话跟随。
*   能够处理阻塞事件（利用 Core 提供的 `send_blocking`）。
