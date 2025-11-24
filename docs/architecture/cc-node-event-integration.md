# CC 节点与事件系统集成设计

> **文档用途**: 定义 CC 智能体节点如何与 Mosaic 事件系统抽象层对接  
> **创建日期**: 2025-11-24  
> **前置文档**: `event-system-spec.md`, `project-understanding-and-tasks.md`

---

## 1. 核心问题

本文档解决以下关键问题：

1. **CC 节点会产生哪些事件？**
2. **CC 节点如何处理接收到的事件？**
3. **事件接收后应该进入哪个会话？如何与上游会话对齐？**
4. **阻塞事件如何实现通用的等待-唤醒机制？**

---

## 2. CC 节点产生的事件

### 2.1 Hook 事件（Claude 运行时 → Mesh）

这些事件由 Claude Code 的 Hook 机制触发，通过我们提供的 HookHandler 捕获并发送到 Mesh：

| 事件类型 | 触发时机 | 典型用途 |
|---------|---------|---------|
| `PreToolUse` | 工具调用前 | 审计、权限控制 |
| `PostToolUse` | 工具调用后 | 日志记录、结果验证 |
| `UserPromptSubmit` | 用户提交输入 | 监控用户意图 |
| `SessionStart` | 会话开始 | 初始化、上下文准备 |
| `SessionEnd` | 会话结束 | 清理、总结 |
| `Stop` | 停止信号 | 中断处理 |
| `PermissionRequest` | 权限请求 | 授权流程 |
| `Notification` | 系统通知 | 状态广播 |

**事件来源**：
- 触发点：Claude CLI/SDK 的 HookRunner 捕获生命周期回调
- 发送方式：通过 `MeshOutbox` 序列化并发送

### 2.2 NodeMessage（主动通信与回复）

- **回复阻塞事件**：`reply_to` 字段指向原事件 ID，包含决策结果（如 `allow/deny/ask`）
- **主动广播**：节点通过 MCP 工具或 CLI 扩展发送业务消息、状态汇报、上下文补充

### 2.3 节点生命周期事件（可选扩展）

- `NodeStateChange`：节点状态切换（idle/program/interactive/background）
- `CapabilityRegistered`：节点向 MeshAdmin 注册能力
- 用途：帮助 MeshContext 构建拓扑与健康视图

---

## 3. 会话对齐机制

### 3.1 核心问题

当节点 A 订阅节点 B 的事件时，关键问题是：**A 用什么粒度来组织会话，以处理来自 B（以及其他上游）的事件流？**

这不是由事件发送方决定的，而是由**订阅关系**在编排时声明的。

### 3.2 SessionTrace：事件中的会话溯源

每个事件都携带上游会话信息（事实描述，非指令）：

```python
class SessionTrace:
    node_id: str                # 产生事件的节点 ID
    upstream_session_id: str    # 上游会话标识
    event_seq: int              # 该会话中的第几个事件
```

**作用**：
- 提供事件的上下文来源
- 为下游的会话对齐策略提供依据
- 不决定下游如何处理

### 3.3 Session Scope：订阅关系中的会话作用域

在订阅关系中声明下游如何组织会话：

```bash
ccm sub <source> <target> "<pattern>" --session-scope <scope> [--session-filter <filter>]
```

#### Session Scope 策略体系

Session Scope 分为两大类：**创建型策略**和**派发型策略**。

##### 创建型策略：按规则创建/复用会话

这些策略根据事件属性计算会话标识，总是创建或复用特定的会话。

| Scope | 含义 | 会话 Key | 典型场景 |
|-------|------|---------|---------|
| `upstream-session` | 上游的一个会话 → 下游的一个会话 | `(upstream_node, session_id)` | 审计节点"跟随"前端会话，保持完整上下文 |
| `per-event` | 每个事件 → 一个新会话 | `event_id` | 把每个事件当作独立任务，互不干扰 |
| `upstream-node` | 上游节点的所有会话 → 下游的一个会话 | `upstream_node` | 为每个上游节点维护一个专门的处理会话 |
| `global` | 所有事件 → 同一个长期会话 | `"global"` | 单一协调者处理所有上游事件 |
| `global:<name>` | 指定名称的全局会话 | `<name>` | 多个订阅共享同一个命名会话 |

##### 派发型策略：从现有会话中选择

这些策略从节点已有的会话中选择一个来处理事件，适用于需要**负载均衡**和**并发处理**的场景。

| Scope | 含义 | 选择规则 | 典型场景 |
|-------|------|---------|---------|
| `random` | 随机派发 | 从现有会话中随机选择 | 无状态任务的简单负载分配 |
| `round-robin` | 轮询派发 | 按顺序依次派发 | 均匀分配负载 |
| `load-balanced` | 负载均衡 | 派发给队列最短的会话 | 计算密集型任务，避免单点过载 |
| `sticky-source` | 粘性源派发 | 同一上游节点的事件总是派发到同一会话 | 需要保持上游上下文连贯性 |

**派发型策略的回退机制**：
- 如果当前没有可用会话，会自动创建一个新的后台会话
- 可以通过 `min_conversations` 配置最少保持的会话数量

#### Session Filter：会话过滤器

控制哪些类型的会话参与事件处理：

| Filter | 含义 | 用途 |
|--------|------|------|
| `any` (默认) | 所有会话 | 前端和后台会话都参与 |
| `backend-only` | 仅后台会话 | 不打扰用户的交互式会话 |
| `interactive-only` | 仅交互式会话 | 只派发给用户正在使用的会话 |
| `interactive-first` | 交互式优先 | 优先派发给前端，无前端则后台 |

#### 完整示例

```bash
# === 创建型策略示例 ===

# 场景 1：审计节点为每个前端会话维护一个审计会话
ccm sub auditor worker "!PreToolUse" --session-scope upstream-session

# 场景 2：日志节点用一个全局会话记录所有事件
ccm sub logger worker "*" --session-scope global

# 场景 3：每个事件独立处理（一次性任务）
ccm sub analyzer worker "PostToolUse" --session-scope per-event

# 场景 4：协调者在同一个会话中处理来自 worker 和 monitor 的事件
ccm sub coordinator worker "*" --session-scope global:ops-bridge
ccm sub coordinator monitor "*" --session-scope global:ops-bridge

# === 派发型策略示例 ===

# 场景 5：高并发日志，轮询派发到后台会话
ccm sub logger worker "*" \
    --session-scope round-robin \
    --session-filter backend-only

# 场景 6：负载均衡的分析任务
ccm sub analyzer worker "PostToolUse" \
    --session-scope load-balanced \
    --session-filter backend-only

# 场景 7：随机派发，但前端会话优先（让用户实时看到事件）
ccm sub monitor worker "*" \
    --session-scope random \
    --session-filter interactive-first

# 场景 8：粘性源派发（同一上游的事件保持上下文）
ccm sub coordinator worker "*" \
    --session-scope sticky-source \
    --session-filter backend-only
```

#### 策略选择指南

| 业务需求 | 推荐策略 | 理由 |
|---------|---------|------|
| 精确审计，需要完整上下文 | `upstream-session` | 每个上游会话独立跟踪 |
| 高并发无状态任务 | `round-robin` + `backend-only` | 均匀分配，避免干扰前端 |
| 计算密集型任务 | `load-balanced` + `backend-only` | 避免单会话过载 |
| 需要上游上下文连贯性 | `sticky-source` | 同一上游的事件在同一会话中 |
| 短生命周期独立任务 | `per-event` | 隔离性好，失败不影响其他 |
| 实时监控与展示 | `random` + `interactive-first` | 用户能看到实时事件流 |
| 全局状态管理 | `global` | 所有事件共享一个会话状态 |

### 3.4 SessionResolver：统一的会话解析

```python
class SessionResolver:
    """统一的会话解析器，处理创建型和派发型策略"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.creation_strategy = CreationStrategy()
        self.dispatch_strategy = DispatchStrategy(session_manager)
    
    async def resolve(
        self,
        event: MeshEvent,
        subscription: Subscription
    ) -> BackendSession:
        """解析目标会话"""
        
        scope = subscription.session_scope
        filter_type = subscription.session_filter or "any"
        
        # 判断策略类型
        if self.is_creation_strategy(scope):
            # 创建型：总是创建/复用特定会话
            sess_id = self.creation_strategy.resolve_session_id(event, scope)
            return self.session_manager.get_or_create(
                session_id=sess_id,
                session_profile=subscription.session_profile,
                session_type="backend"
            )
        
        elif self.is_dispatch_strategy(scope):
            # 派发型：从现有会话中选择
            session = self.dispatch_strategy.select_session(
                event, scope, filter_type
            )
            
            if session is None:
                # 没有可用会话，回退到创建新会话
                sess_id = f"auto-{generate_id()}"
                session = self.session_manager.get_or_create(
                    session_id=sess_id,
                    session_profile=subscription.session_profile,
                    session_type="backend"
                )
            
            return session
        
        else:
            raise ValueError(f"Unknown session scope: {scope}")
    
    def is_creation_strategy(self, scope: str) -> bool:
        """判断是否是创建型策略"""
        return scope in [
            "per-event",
            "upstream-session",
            "upstream-node"
        ] or scope.startswith("global")
    
    def is_dispatch_strategy(self, scope: str) -> bool:
        """判断是否是派发型策略"""
        return scope in [
            "random",
            "round-robin",
            "load-balanced",
            "sticky-source"
        ]


class CreationStrategy:
    """创建型策略：根据规则创建/复用会话"""
    
    def resolve_session_id(
        self, 
        event: MeshEvent,
        scope: str
    ) -> str:
        """计算目标会话 ID"""
        
        if scope == "per-event":
            return event.event_id
        
        elif scope == "upstream-session":
            trace = event.session_trace
            return f"{trace.node_id}:{trace.upstream_session_id}"
        
        elif scope == "upstream-node":
            return f"node:{event.session_trace.node_id}"
        
        elif scope.startswith("global"):
            name = scope.split(":", 1)[1] if ":" in scope else "global"
            return f"global:{name}"
        
        else:
            raise ValueError(f"Unknown scope: {scope}")


class DispatchStrategy:
    """派发型策略：从现有会话中选择"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.round_robin_index = 0
    
    def select_session(
        self,
        event: MeshEvent,
        strategy: str,
        filter_type: str = "any"
    ) -> Optional[BackendSession]:
        """从现有会话中选择一个"""
        
        # 1. 获取符合过滤条件的会话
        candidates = self.get_filtered_sessions(filter_type)
        
        if not candidates:
            return None  # 没有可用会话，需要创建
        
        # 2. 根据策略选择
        if strategy == "random":
            return random.choice(candidates)
        
        elif strategy == "round-robin":
            selected = candidates[self.round_robin_index % len(candidates)]
            self.round_robin_index += 1
            return selected
        
        elif strategy == "load-balanced":
            # 选择队列最短的会话
            return min(candidates, key=lambda s: s.pending_events_count)
        
        elif strategy == "sticky-source":
            # 根据上游节点 ID 一致性哈希
            source_node = event.session_trace.node_id
            index = hash(source_node) % len(candidates)
            return candidates[index]
        
        else:
            raise ValueError(f"Unknown dispatch strategy: {strategy}")
    
    def get_filtered_sessions(
        self, 
        filter_type: str
    ) -> List[BackendSession]:
        """获取符合过滤条件的会话"""
        
        all_sessions = self.session_manager.get_all_sessions()
        
        if filter_type == "backend-only":
            # 只返回后台会话（排除 interactive）
            return [s for s in all_sessions if s.type == "backend"]
        
        elif filter_type == "interactive-only":
            # 只返回前端会话
            return [s for s in all_sessions if s.type == "interactive"]
        
        elif filter_type == "interactive-first":
            # 前端会话优先
            interactive = [s for s in all_sessions if s.type == "interactive"]
            if interactive:
                return interactive
            return [s for s in all_sessions if s.type == "backend"]
        
        elif filter_type == "any":
            # 所有会话
            return all_sessions
        
        else:
            raise ValueError(f"Unknown filter: {filter_type}")
```

---

## 4. 阻塞事件的等待-唤醒机制

### 4.1 设计原则

**核心需求**：高层代码不应该关心"到底是 Hook 在等待还是会话在等待"，只需要知道"这是一个阻塞事件，需要等待回复"。

**解决方案**：引入通用的 `EventWaiter` 抽象，将阻塞等待与具体的业务逻辑解耦。

### 4.2 EventWaiter：抽象的等待点

```python
class EventWaiter:
    """抽象的等待点，不关心底层是 Hook、会话还是其他机制"""
    
    def __init__(self, event_id: str):
        self.event_id = event_id
        self.future = asyncio.Future()
    
    async def wait(self, timeout: float) -> Any:
        """阻塞等待，直到被唤醒或超时"""
        try:
            return await asyncio.wait_for(self.future, timeout)
        except asyncio.TimeoutError:
            raise EventTimeoutError(self.event_id, timeout)
    
    def resolve(self, result: Any):
        """唤醒等待者"""
        if not self.future.done():
            self.future.set_result(result)
    
    def reject(self, error: Exception):
        """以错误唤醒等待者"""
        if not self.future.done():
            self.future.set_exception(error)
```

### 4.3 WaiterRegistry：全局等待点注册表

```python
class WaiterRegistry:
    """管理所有等待点"""
    
    def __init__(self):
        self._waiters: Dict[str, EventWaiter] = {}
    
    def register(self, event_id: str) -> EventWaiter:
        """注册一个等待点"""
        waiter = EventWaiter(event_id)
        self._waiters[event_id] = waiter
        return waiter
    
    def get(self, event_id: str) -> Optional[EventWaiter]:
        """获取等待点"""
        return self._waiters.get(event_id)
    
    def resolve(self, event_id: str, result: Any):
        """触发等待点"""
        waiter = self._waiters.get(event_id)
        if waiter:
            waiter.resolve(result)
            self.unregister(event_id)
    
    def unregister(self, event_id: str):
        """清理等待点"""
        self._waiters.pop(event_id, None)
```

### 4.4 发送阻塞事件

```python
class MeshOutbox:
    def __init__(self, waiter_registry: WaiterRegistry):
        self.waiter_registry = waiter_registry
    
    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float = 30
    ) -> List[Any]:
        """发送阻塞事件并等待回复"""
        
        # 1. 查询所有阻塞订阅者
        blocking_subscribers = self.get_blocking_subscribers(event.type)
        
        if not blocking_subscribers:
            # 没有阻塞订阅者，直接发送
            await self.send(event)
            return []
        
        # 2. 为每个订阅者创建独立事件和 Waiter
        waiters = []
        for subscriber in blocking_subscribers:
            sub_event = event.clone()
            sub_event.event_id = generate_event_id()
            sub_event.target_id = subscriber
            
            # 注册 Waiter
            waiter = self.waiter_registry.register(sub_event.event_id)
            waiters.append((sub_event, waiter))
        
        # 3. 并发发送所有事件
        await asyncio.gather(*[
            self.send(sub_event) 
            for sub_event, _ in waiters
        ])
        
        # 4. 等待所有回复（或超时）
        results = await asyncio.gather(*[
            waiter.wait(timeout) 
            for _, waiter in waiters
        ], return_exceptions=True)
        
        # 5. 返回结果
        return results
    
    async def send(self, event: MeshEvent):
        """发送非阻塞事件"""
        # 写入数据库
        await EventRepository.save(event)
        # 通过 UDS 唤醒接收方
        await self.signal_client.notify(event.target_id)
```

### 4.5 接收回复并触发 Waiter

```python
class MeshInbox:
    def __init__(self, waiter_registry: WaiterRegistry):
        self.waiter_registry = waiter_registry
    
    async def handle_incoming_event(self, event: MeshEvent):
        """处理接收到的事件"""
        
        # 如果是回复消息，检查是否有等待者
        if isinstance(event, NodeMessage) and event.reply_to:
            waiter = self.waiter_registry.get(event.reply_to)
            if waiter:
                # 触发等待者
                waiter.resolve(event.content)
                # 清理 Waiter
                self.waiter_registry.unregister(event.reply_to)
                # ACK 事件
                await self.ack(event)
                return
        
        # 普通事件，交给 EventProcessor 处理
        await self.event_processor.process(event)
```

### 4.6 在 Hook 中使用

```python
class HookHandler:
    def __init__(self, outbox: MeshOutbox):
        self.outbox = outbox
    
    async def handle_pre_tool_use(self, context: HookContext) -> HookResult:
        """处理 PreToolUse Hook"""
        
        # 创建事件
        event = PreToolUseEvent(
            source_id=self.node_id,
            tool_name=context.tool_name,
            tool_input=context.tool_input,
            conversation_trace=self.get_current_trace()
        )
        
        # 查询是否有阻塞订阅者
        if self.has_blocking_subscribers("PreToolUse"):
            # 发送阻塞事件（内部自动注册 Waiter 并等待）
            replies = await self.outbox.send_blocking(event, timeout=30)
            
            # 聚合回复
            decision = self.aggregate_decisions(replies)
            
            return HookResult(
                permissionDecision=decision.permission,
                permissionDecisionReason=decision.reason
            )
        else:
            # 非阻塞发送
            await self.outbox.send(event)
            return HookResult(permissionDecision="allow")
    
    def aggregate_decisions(self, replies: List[Any]) -> Decision:
        """聚合多个订阅者的回复（一票否决制）"""
        denials = []
        asks = []
        
        for reply in replies:
            if isinstance(reply, Exception):
                # 超时或错误，视为拒绝
                denials.append("订阅者超时未响应")
            elif reply.get("decision") == "deny":
                denials.append(reply.get("reason", "未提供理由"))
            elif reply.get("decision") == "ask":
                asks.append(reply.get("prompt", "需要确认"))
        
        # 一票否决
        if denials:
            return Decision(
                permission="deny",
                reason="拒绝理由：" + "; ".join(denials)
            )
        
        # 任何一个要求询问
        if asks:
            return Decision(
                permission="ask",
                reason="需要确认：" + "; ".join(asks)
            )
        
        # 全部允许
        return Decision(permission="allow")
```

### 4.7 抽象层次图

```
┌─────────────────────────────────────┐
│  Hook / Session / 业务逻辑           │  ← 不知道 Waiter 的存在
│  只调用 send_blocking() 或 send()   │     只关心"等待回复"
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  MeshOutbox / MeshInbox              │  ← 管理 Waiter 的注册和触发
│  - send_blocking() 注册 Waiter       │     处理阻塞语义
│  - handle_reply() 触发 Waiter        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  WaiterRegistry                      │  ← 全局等待点注册表
│  - register(event_id) → Waiter       │     解耦等待者和唤醒者
│  - resolve(event_id, result)         │
└──────────────────────────────────────┘
```

---

## 5. Backend Session 与 Interactive Agent

### 5.1 两种会话模式

CC 节点支持两种会话模式，用于处理不同的场景需求：

#### Backend Session（后台会话）

**定义**：在 Node Runtime 进程内部运行的会话，使用 claude-agent-sdk 创建和管理。

**特点**：
- 不需要独立的 Claude Code 进程
- 轻量级，适合大量并发会话
- 完全由 Node Runtime 控制生命周期
- 适用于自动化任务、事件驱动处理

**实现**：
```python
class BackendSession:
    """后台会话（在 Node Runtime 内部运行）"""
    
    def __init__(
        self, 
        session_id: str,
        agent_sdk: AgentSDK,
        profile: SessionProfile,
        conv_type: str = "backend"
    ):
        self.session_id = session_id
        self.type = conv_type  # "backend" 或 "interactive"
        
        # 使用 claude-agent-sdk 创建会话
        self.session = agent_sdk.create_session(
            system_prompt=profile.system_prompt,
            tools=profile.tools
        )
        
        # 用于负载均衡
        self.pending_events_count = 0
        self.last_activity = datetime.now()
    
    async def process_event(self, event: MeshEvent):
        """处理事件"""
        self.pending_events_count += 1
        
        try:
            # 将事件格式化为消息
            message = self.format_event_as_message(event)
            
            # 发送到 Claude
            response = await self.session.send_message(message)
            
            # Claude 可能调用 MCP 工具（如 respond_to_pre_tool_use）
            # MCP 工具会通过 Node Runtime 的 outbox 发送回复
        finally:
            self.pending_events_count -= 1
            self.last_activity = datetime.now()
```

**生命周期**：
- 由 SessionResolver 按需创建
- 根据 session_scope 决定复用还是销毁
- 可以通过 TTL 机制自动清理不活跃会话

#### Interactive Agent（交互式智能体）

**定义**：独立的 Claude Code 进程，由用户或外部启动，通过 IPC 与 Node Runtime 协作。

**特点**：
- 独立的 Claude Code 进程
- 用户可以直接交互（通过终端）
- 由用户控制启动和停止
- 可以"占据"某个 session_id，接收该会话的事件

**实现**：
```python
class InteractiveAgentProxy:
    """代表一个外部的 Claude Code 进程"""
    
    def __init__(
        self, 
        agent_id: str, 
        session_id: str, 
        ipc_connection: IPCConnection
    ):
        self.agent_id = agent_id
        self.session_id = session_id  # 该 Agent 声明的会话 ID
        self.ipc_connection = ipc_connection
        self.type = "interactive"
    
    async def inject_event(self, event: MeshEvent):
        """将事件通过 IPC 投递给外部进程"""
        await self.ipc_connection.send({
            "type": "event_delivery",
            "event": event.to_dict()
        })
```

**启动流程**：
```bash
# 用户启动交互式会话
ccm chat worker

# CLI 做以下事情：
# 1. 连接到 worker 的 Node Runtime
# 2. 请求分配 agent_id 和 session_id
# 3. 准备 Agent 配置（Hook/MCP 指向 Node Runtime）
# 4. 启动独立的 Claude Code 进程
# 5. 进程通过 Hook/MCP 自动连接并注册到 Node Runtime
```

### 5.2 会话路由逻辑

```python
class CCNodeRuntime:
    async def handle_incoming_event(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ):
        """处理入站事件"""
        
        # 1. 解析目标 session_id
        target_session_id = self.session_resolver.resolve(event, subscription)
        
        # 2. 检查是否有外部 Interactive Agent 占据该会话
        interactive_agent = self.external_agents.get_by_session(target_session_id)
        
        if interactive_agent:
            # 投递给外部 Agent Process（通过 IPC）
            await interactive_agent.inject_event(event)
        else:
            # 使用内部 Backend Session 处理
            session = self.session_manager.get_or_create(
                session_id=target_session_id,
                session_profile=subscription.session_profile,
                conv_type="backend"
            )
            await session.process_event(event)
```

**路由优先级**：
1. 如果存在占据该 session_id 的 Interactive Agent → 派发给它
2. 否则 → 使用 Backend Session

### 5.3 使用场景对比

| 场景 | 推荐模式 | 理由 |
|------|---------|------|
| 高并发事件处理 | Backend Session | 轻量级，无需启动大量进程 |
| 自动化审计/日志 | Backend Session | 完全自动化，无需人工干预 |
| 用户调试和观察 | Interactive Agent | 用户可以实时看到和干预 |
| 复杂决策需要人工确认 | Interactive Agent | 用户可以参与决策 |
| per-event 模式 | Backend Session | 频繁创建销毁，进程开销大 |
| upstream-session（长期） | 两者皆可 | 取决于是否需要用户参与 |

### 5.4 SessionManager 实现

```python
class SessionManager:
    """管理节点内部的后台会话和外部 Agent"""
    
    def __init__(self, agent_sdk: AgentSDK):
        self.agent_sdk = agent_sdk
        self.backend_sessions: Dict[str, BackendSession] = {}
        self.interactive_agents: Dict[str, InteractiveAgentProxy] = {}
    
    def get_or_create(
        self, 
        session_id: str,
        session_profile: str,
        conv_type: str = "backend"
    ) -> BackendSession:
        """获取或创建后台会话"""
        
        if session_id in self.backend_sessions:
            return self.backend_sessions[session_id]
        
        # 创建新会话
        session = BackendSession(
            session_id=session_id,
            agent_sdk=self.agent_sdk,
            profile=self.load_profile(session_profile),
            conv_type=conv_type
        )
        
        self.backend_sessions[session_id] = session
        return session
    
    def register_interactive_agent(
        self,
        agent_id: str,
        session_id: str,
        ipc_connection: IPCConnection
    ):
        """注册外部 Interactive Agent"""
        agent = InteractiveAgentProxy(agent_id, session_id, ipc_connection)
        self.interactive_agents[session_id] = agent
    
    def get_all_sessions(self) -> List[BackendSession]:
        """获取所有会话（用于派发型策略）"""
        # 返回 Backend Session 和 Interactive Agent（统一接口）
        return list(self.backend_sessions.values()) + \
               list(self.interactive_agents.values())
```

---

## 6. 事件处理流程

### 6.1 EventProcessor：事件分发与处理

```python
class EventProcessor:
    """负责将接收到的事件分发到正确的处理通道"""
    
    def __init__(
        self, 
        session_manager: SessionManager,
        waiter_registry: WaiterRegistry
    ):
        self.session_manager = session_manager
        self.waiter_registry = waiter_registry
    
    async def process(self, event: MeshEvent, subscription: Subscription):
        """处理接收到的事件"""
        
        # 1. 解析应该使用哪个会话
        session = self.session_manager.resolve_session(event, subscription)
        
        # 2. 将事件转换为会话消息
        message = self.format_event_as_message(event, subscription)
        
        # 3. 发送到会话
        await session.send_message(message)
        
        # 注：如果是阻塞订阅，Claude 会调用 MCP 工具回复
        #     MCP 工具内部会调用 outbox.reply()
        #     reply() 会触发发送方的 Waiter
    
    def format_event_as_message(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> str:
        """将事件格式化为 Claude 可理解的消息"""
        
        if isinstance(event, PreToolUseEvent):
            return f"""
收到工具调用审查请求：
- 来源节点：{event.source_id}
- 工具名称：{event.tool_name}
- 工具参数：{event.tool_input}
- 会话上下文：{event.conversation_trace.session_id}

请审查该工具调用，并使用 respond_to_pre_tool_use 工具回复。
"""
        
        elif isinstance(event, PostToolUseEvent):
            return f"""
工具调用完成通知：
- 来源节点：{event.source_id}
- 工具名称：{event.tool_name}
- 执行结果：{event.result}
"""
        
        # 其他事件类型...
```

### 6.2 MCP 工具：回复阻塞事件

```python
@mcp.tool()
async def respond_to_pre_tool_use(
    event_id: str,
    decision: Literal["allow", "deny", "ask"],
    reason: Optional[str] = None,
    prompt: Optional[str] = None
):
    """回复 PreToolUse 事件"""
    
    # 创建回复消息
    reply = NodeMessage(
        source_id=current_node_id,
        target_id=original_event.source_id,
        reply_to=event_id,
        content={
            "decision": decision,
            "reason": reason,
            "prompt": prompt
        }
    )
    
    # 发送回复（会触发发送方的 Waiter）
    await outbox.send(reply)
    
    return f"已回复：{decision}"
```

---

## 7. 完整示例：工具审计流程

### 7.1 场景设置

```bash
# 创建节点
ccm create worker --path ./worker
ccm create auditor --path ./auditor

# 建立订阅关系
ccm sub auditor worker "!PreToolUse" --session-scope upstream-session
```

### 7.2 执行流程

#### Step 1: Worker 触发工具调用

```python
# 在 worker 的 Claude 会话中，用户输入：
# "请删除 temp.txt 文件"

# Claude 决定调用 delete_file 工具
# → 触发 PreToolUse Hook
```

#### Step 2: Hook 发送阻塞事件

```python
# worker 的 HookHandler
async def handle_pre_tool_use(context):
        event = PreToolUseEvent(
            source_id="worker",
            tool_name="delete_file",
            tool_input={"path": "temp.txt"},
            session_trace=SessionTrace(
                node_id="worker",
                upstream_session_id="sess_worker_123",
                event_seq=5
            )
        )
    
    # 发送阻塞事件（内部注册 Waiter）
    replies = await outbox.send_blocking(event, timeout=30)
    
    # 等待 auditor 回复...
```

#### Step 3: Auditor 接收并处理

```python
# auditor 的 EventProcessor
async def process(event, subscription):
    # session_scope = "upstream-session"
    # → key = ("worker", "sess_worker_123")
    # → 为 worker 的这个会话创建/复用一个审计会话
    
    session = session_manager.resolve_session(event, subscription)
    
    # 在审计会话中注入消息
    await session.send_message("""
收到工具调用审查请求：
- 来源：worker
- 工具：delete_file
- 参数：{"path": "temp.txt"}

请审查该操作。
""")
```

#### Step 4: Auditor 的 Claude 做决策

```python
# auditor 的 Claude 会话中：
# Claude: "这是一个删除操作，我需要检查文件重要性..."
# Claude 调用 MCP 工具：
# respond_to_pre_tool_use(
#     event_id="evt_123",
#     decision="deny",
#     reason="temp.txt 包含重要的临时数据，不应删除"
# )
```

#### Step 5: 回复触发 Waiter

```python
# MCP 工具内部
async def respond_to_pre_tool_use(...):
    reply = NodeMessage(
        source_id="auditor",
        target_id="worker",
        reply_to="evt_123",
        content={"decision": "deny", "reason": "..."}
    )
    
    await outbox.send(reply)
    # → worker 的 Inbox 收到回复
    # → 查找 Waiter(evt_123)
    # → waiter.resolve(reply.content)
    # → worker 的 send_blocking() 返回
```

#### Step 6: Worker 的 Hook 返回结果

```python
# worker 的 HookHandler
async def handle_pre_tool_use(context):
    # ...
    replies = await outbox.send_blocking(event, timeout=30)
    # ← 这里被唤醒，收到 auditor 的回复
    
    decision = aggregate_decisions(replies)
    # → decision.permission = "deny"
    
    return HookResult(
        permissionDecision="deny",
        permissionDecisionReason="temp.txt 包含重要数据"
    )
    
    # → Claude Code 阻止工具调用
    # → 在 worker 的会话中显示拒绝理由
```

---

## 8. 订阅关系的完整表达

### 8.1 CLI 语法

```bash
ccm sub <source> <target> "<pattern>" [options]

Options:
  --session-scope <scope>      会话作用域策略
                               
                               创建型策略（按规则创建/复用会话）:
                                 - upstream-session (默认)
                                 - per-event
                                 - upstream-node
                                 - global[:<name>]
                               
                               派发型策略（从现有会话中选择）:
                                 - random
                                 - round-robin
                                 - load-balanced
                                 - sticky-source
  
  --session-filter <filter>    会话过滤器（仅对派发型策略有效）
                               - any (默认，所有会话)
                               - backend-only (仅后台会话)
                               - interactive-only (仅交互式会话)
                               - interactive-first (优先交互式)
  
  --session-profile <name>     会话配置文件（定义系统提示词、工具等）
  
  --min-conversations <n>      最少保持的会话数（仅派发型策略，默认 1）
  
  --max-conversations <n>      最多会话数（仅派发型策略，默认 10）
```

### 8.2 数据库 Schema

```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,           -- 订阅者（下游）
    target_id TEXT NOT NULL,           -- 被订阅者（上游）
    event_pattern TEXT NOT NULL,       -- 事件模式（支持 !EventName 表示阻塞）
    
    -- Session 策略配置
    session_scope TEXT DEFAULT 'upstream-session',  -- 创建型或派发型策略
    session_filter TEXT DEFAULT 'any',              -- 会话过滤器
    session_profile TEXT DEFAULT 'default',         -- 会话配置文件
    
    -- 派发型策略的额外配置
    min_conversations INTEGER DEFAULT 1,            -- 最少保持的会话数
    max_conversations INTEGER DEFAULT 10,           -- 最多会话数
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, event_pattern)
);
```

### 8.3 订阅模式解析

```python
class SubscriptionPattern:
    """解析订阅模式"""
    
    @staticmethod
    def parse(pattern: str) -> Tuple[bool, List[str]]:
        """
        解析事件模式
        
        Returns:
            (is_blocking, event_types)
        
        Examples:
            "!PreToolUse" → (True, ["PreToolUse"])
            "PreToolUse,PostToolUse" → (False, ["PreToolUse", "PostToolUse"])
            "*" → (False, ["*"])
        """
        if pattern.startswith("!"):
            return (True, [pattern[1:]])
        else:
            return (False, pattern.split(","))
```

---

## 9. 实现要点

### 9.1 MeshClient 集成

```python
class CCNodeRuntime:
    """CC 节点运行时"""
    
    def __init__(self, node_id: str, mesh_id: str):
        self.node_id = node_id
        self.mesh_id = mesh_id
        
        # 事件系统组件
        self.waiter_registry = WaiterRegistry()
        self.outbox = MeshOutbox(self.waiter_registry)
        self.inbox = MeshInbox(self.waiter_registry)
        
        # 会话管理
        self.session_manager = SessionManager()
        self.event_processor = EventProcessor(
            self.session_manager,
            self.waiter_registry
        )
        
        # Hook 处理
        self.hook_handler = HookHandler(self.outbox)
    
    async def start(self):
        """启动节点"""
        # 启动 Inbox 监听
        await self.inbox.start()
        
        # 注册 Hook
        self.register_hooks()
        
        # 启动事件处理循环
        asyncio.create_task(self.event_loop())
    
    async def event_loop(self):
        """事件处理循环"""
        async for event in self.inbox:
            subscription = await self.get_subscription_for_event(event)
            await self.event_processor.process(event, subscription)
            await self.inbox.ack(event)
```

### 9.2 Hook 注册

```python
def register_hooks(self):
    """注册 Claude Code Hooks"""
    
    @hook("PreToolUse")
    async def on_pre_tool_use(context):
        return await self.hook_handler.handle_pre_tool_use(context)
    
    @hook("PostToolUse")
    async def on_post_tool_use(context):
        return await self.hook_handler.handle_post_tool_use(context)
    
    # 其他 Hooks...
```

### 9.3 MCP 工具注册

```python
def register_mcp_tools(self):
    """注册 MCP 工具"""
    
    @mcp.tool()
    async def respond_to_pre_tool_use(event_id, decision, reason=None):
        return await self.handle_respond_to_pre_tool_use(
            event_id, decision, reason
        )
    
    @mcp.tool()
    async def send_message_to_node(target_id, content):
        return await self.handle_send_message(target_id, content)
```

---

## 10. 与 Program 模式的关系

### 10.1 Program 模式的特殊性

在 Program 模式下：
- **MeshClient 只读**：可以查询拓扑和语义，但不能发送/接收事件
- **会话独立**：不与任何上游会话对齐
- **目的**：配置节点的角色和行为，而不是处理实际事件

### 10.2 系统提示词注入

```python
def generate_system_prompt(node_id: str, mode: str) -> str:
    """生成系统提示词"""
    
    context = MeshContext.get_topology_context(node_id)
    
    if mode == "program":
        return f"""
你是 Mesh 网络中的 {node_id} 节点。

你的订阅关系：
{format_subscriptions(context.subscriptions)}

注意：当前处于 Program 模式，Mesh 功能已禁用。
请与用户讨论你的职责和工作方式，并将配置写入 CLAUDE.md。
"""
    
    elif mode == "background":
        return f"""
你是 Mesh 网络中的 {node_id} 节点（后台模式）。

你的职责：
{load_program_config(node_id)}

你订阅了以下节点的事件：
{format_subscriptions(context.subscriptions)}

当收到事件时，请根据你的职责进行处理，并使用相应的 MCP 工具回复。
"""
    
    elif mode == "interactive":
        return f"""
你是 Mesh 网络中的 {node_id} 节点（交互模式）。

你的职责：
{load_program_config(node_id)}

注意：你的行为可能被以下节点监督：
{format_subscribers(context.subscribers)}
"""
```

---

## 11. 后续工作

### 11.1 需要实现的组件

1. **WaiterRegistry**：全局等待点注册表
2. **SessionManager**：会话解析与管理
3. **EventProcessor**：事件分发与处理
4. **HookHandler**：Hook 事件处理
5. **MCP 工具集**：respond_to_*, send_message_to_node 等

### 11.2 需要扩展的文档

1. **event-system-spec.md**：
   - 添加 `SessionTrace` 定义
   - 添加 `session_scope` 字段到订阅关系
   
2. **mcp-tools-spec.md**（新建）：
   - 定义所有 MCP 工具的签名和语义
   - 说明工具如何与事件系统交互

3. **session-management-spec.md**（新建）：
   - 详细说明会话的创建、复用、销毁策略
   - 定义 session_profile 的结构

### 11.3 需要测试的场景

1. **单一阻塞订阅者**：worker → auditor
2. **多个阻塞订阅者**：worker → auditor1, auditor2（一票否决）
3. **混合订阅**：worker → auditor（阻塞）+ logger（非阻塞）
4. **会话对齐**：
   - upstream-session：每个上游会话对应一个下游会话
   - per-event：每个事件一个新会话
   - global：所有事件共享一个会话
5. **超时处理**：订阅者未及时回复
6. **级联事件**：auditor 处理事件时也产生事件

---

## 12. 总结

### 12.1 核心设计原则

1. **会话对齐由订阅关系声明**：通过 `session_scope` 表达下游如何组织会话
2. **阻塞等待抽象化**：通过 `EventWaiter` 解耦业务逻辑与等待机制
3. **事件携带溯源信息**：通过 `SessionTrace` 提供上下文来源
4. **高层不关心实现细节**：Hook、会话、服务都使用相同的抽象接口

### 12.2 关键抽象

| 抽象 | 职责 | 关键方法 |
|------|------|---------|
| `SessionTrace` | 事件溯源 | `node_id`, `upstream_session_id`, `event_seq` |
| `SessionManager` | 会话管理 | `get_or_create()`, `get_all_sessions()` |
| `SessionResolver` | 会话解析 | `resolve()`, `is_creation_strategy()` |
| `EventWaiter` | 阻塞等待 | `wait()`, `resolve()` |
| `WaiterRegistry` | 等待点注册 | `register()`, `resolve()` |
| `EventProcessor` | 事件分发 | `process()`, `format_event_as_message()` |
| `HookHandler` | Hook 处理 | `handle_pre_tool_use()`, `aggregate_decisions()` |

### 12.3 订阅关系的表达力

通过 `session_scope`（创建型 + 派发型）、`session_filter` 和阻塞模式（`!` 前缀）的组合，可以表达：
- 一对一会话镜像（upstream-session）
- 每事件独立处理（per-event）
- 多源事件聚合（global）
- 负载均衡处理（round-robin, load-balanced）
- 粘性源路由（sticky-source）
- 阻塞审计（!EventName）
- 非阻塞日志（EventName）
- 前端隔离（backend-only）
- 用户参与（interactive-first）

这套机制既简洁又强大，能够覆盖各种协作、并发和交互场景。

---

**文档结束**

