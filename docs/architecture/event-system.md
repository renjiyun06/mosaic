# 事件系统详情

## 1. 事件模型

### 1.1 MeshEvent 结构
事件是系统中的核心数据单元。

```python
class MeshEvent(BaseModel):
    event_id: str          # 全局唯一 ID
    mesh_id: str           # 所属 Mesh 实例
    source_id: str         # 发送节点 ID
    target_id: str         # 接收节点 ID
    type: str              # 事件类型 (如 "PreToolUse")
    payload: Dict[str, Any] # 事件内容
    created_at: datetime
    session_trace: Optional[SessionTrace] # 上游会话追踪
```

## 2. Core 层的事件处理

所有的事件路由、分发和同步逻辑都由 `mosaic.core` 模块内部实现，对业务节点透明。

### 2.1 发送端分发 (Sender-side Dispatch)
1.  节点调用 `self.send(event)`。
2.  Core 查询 `Registry` (原 Storage) 获取订阅关系。
3.  Core 根据订阅列表，为每个订阅者生成一个副本事件。
4.  Core 调用 `Transport` 将副本写入数据库并发送信号。

### 2.2 接收端循环 (Receiver Loop)
1.  `BaseNode` 的主循环轮询 `Transport`。
2.  获取 `EventEnvelope`。
3.  调用子类的 `process_event()`。
4.  根据执行结果提交 `ACK` 或 `NACK`。

### 2.3 阻塞等待 (Request-Response)
Core 提供 `WaiterRegistry` 支持同步语义。
*   `self.send_blocking(event)`:
    1.  Core 生成唯一 `event_id` 并注册 Waiter。
    2.  发送事件。
    3.  挂起当前协程 (Future)。
    4.  收到 `reply_to` 匹配的消息时，唤醒协程并返回结果。

## 3. 智能体节点的会话路由

对于 **CC Agent** 等智能体节点，`process_event` 的内部实现包含了一层额外的路由逻辑。这部分逻辑属于 **节点实现层 (Nodes Layer)**，复用 Core 提供的基础能力。

### 3.1 路由策略 (Strategy)
位于 `mosaic.nodes.agent.routing`。
*   **Mirroring**: 1:1 跟随上游会话。
*   **Tasking**: 每个事件独立处理。
*   **Aggregation**: 汇聚到长期会话。

### 3.2 流程
1.  Core 调用 `CCNode.process_event(event)`。
2.  CCNode 调用 `SessionRouter` 计算目标 `session_id`。
3.  CCNode 获取对应的 `BackendSession`。
4.  CCNode 将事件投递给 Session 进行 LLM 推理。
