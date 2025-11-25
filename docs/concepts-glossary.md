# Mosaic 概念词汇表

> **文档用途**: 定义 Mosaic 系统中的所有核心概念，建立统一的术语体系  
> **创建日期**: 2025-11-24  
> **目标读者**: 开发者、架构师、用户

---

## 1. 概述

本文档定义 Mosaic 系统中的所有核心概念，包括：
- **层次关系**：从系统到进程到会话的完整层级
- **术语对照**：中英文对照和缩写
- **边界划分**：明确各概念的职责范围

**设计原则**：
1. 每个概念有清晰的定义和边界
2. 避免术语重叠和歧义
3. 层次清晰，便于理解
4. 适合作为沟通基础

---

## 2. 系统层概念

### 2.1 Mosaic

**定义**：整个多智能体协作系统的名称，是本项目的产品名。

**别名**：无（不再使用 Claude Code Mesh / CCM）

**层级**：最顶层

---

### 2.2 Mesh Instance（Mesh 实例）

**定义**：一个独立的 Mosaic 系统实例，包含多个节点和它们的订阅关系。

**特点**：
- 有唯一的 `mesh_id`
- 在数据库中通过 `mesh_id` 字段隔离
- 有独立的 Daemon 进程
- 有独立的 Socket 目录、日志目录
- 不同 Mesh 实例在逻辑上完全隔离

**数据存储**：
- **统一数据库**：所有 Mesh 共享 `~/.mosaic/mosaic.db`
- **数据隔离**：通过 `mesh_id` 字段区分
- **独立目录**：`~/.mosaic/<mesh_id>/` 存放 Socket、日志等运行时数据

**生命周期**：
- 创建：`ccm init --mesh-id <mesh_id>`
- 启动：`ccm daemon start --mesh-id <mesh_id>`
- 停止：`ccm daemon stop --mesh-id <mesh_id>`

**示例**：
```bash
# 创建两个独立的 Mesh 实例
ccm init --mesh-id dev-mesh
ccm init --mesh-id prod-mesh

# 目录结构
~/.mosaic/
├── mosaic.db              # 统一数据库（包含所有 Mesh 的数据）
├── dev-mesh/              # dev-mesh 运行时目录
│   ├── daemon.pid
│   ├── daemon.sock
│   ├── sockets/
│   └── logs/
└── prod-mesh/             # prod-mesh 运行时目录
    ├── daemon.pid
    ├── daemon.sock
    ├── sockets/
    └── logs/
```

---

### 2.3 Mesh Topology（Mesh 拓扑）

**定义**：Mesh 实例中所有节点和订阅关系组成的有向图。

**组成**：
- 节点集合：`{Node1, Node2, ...}`
- 订阅关系集合：`{Sub1, Sub2, ...}`

**查询**：
```bash
ccm topology           # 查看当前 Mesh 的拓扑
ccm topology --graph   # 可视化拓扑图
```

---

## 3. 进程层概念

### 3.1 Mosaic Daemon Process（Daemon 进程）

**定义**：Mesh 实例的守护进程，负责监控和管理该 Mesh 中的所有 Node Runtime Process。

**关键特性**：
- 每个 Mesh 实例有一个 Daemon 进程
- 常驻运行
- 提供控制接口：`~/.mosaic/<mesh_id>/daemon.sock`
- 记录 PID：`~/.mosaic/<mesh_id>/daemon.pid`

**职责**：
1. 启动和停止 Node Runtime Process
2. 监控进程健康状态
3. 自动重启崩溃的进程
4. 提供节点状态查询接口

**不负责**：
- 事件路由和分发（由 Node Runtime 负责）
- 业务逻辑（由 Agent 负责）

**命名约定**：`mosaic-daemon-{mesh_id}`

---

### 3.2 Node Runtime Process（节点运行时进程）

**定义**：事件系统要求的"一节点一进程"，代表节点在 Mesh 中的实体。

**关键特性**：
- 每个节点有一个 Runtime 进程
- 常驻运行（由 Daemon 管理）
- 持有事件系统接口：MeshInbox、MeshOutbox
- 管理该节点的所有会话（Backend Conversation）
- 提供 IPC 接口：`/tmp/mosaic-node-{node_id}.sock`

**职责**：
1. 接收和发送事件（通过 MeshInbox/Outbox）
2. 管理 Backend Conversation（内部会话）
3. 注册和管理 Interactive Agent（外部进程）
4. 路由事件到正确的会话
5. 执行 Hook 处理逻辑

**不负责**：
- 实际的智能体推理（由 Agent 负责）
- 用户交互（由 Interactive Agent 负责）

**命名约定**：`node-runtime-{node_id}`

**实现**：`mosaic.nodes.cc.runtime.CCNodeRuntime`

---

### 3.3 Agent Process（智能体进程）

**定义**：实际运行 Claude Code 的进程，执行智能体推理和工具调用。

**类型**：

#### 3.3.1 Backend Agent Process（后台智能体进程）

**定义**：在 Node Runtime 内部使用 claude-agent-sdk 创建的智能体会话，不是独立进程。

**特点**：
- 不需要独立的 Claude Code 进程
- 轻量级，适合大量并发
- 完全由 Node Runtime 管理生命周期
- 用于自动化任务、事件驱动处理

**实现**：`mosaic.nodes.cc.backend_session.BackendSession`

#### 3.3.2 Interactive Agent Process（交互式智能体进程）

**定义**：独立的 Claude Code 进程，由用户或 CLI 启动，通过 IPC 与 Node Runtime 协作。

**特点**：
- 独立的 Claude Code 进程
- 用户可以直接交互（通过终端）
- 生命周期由用户控制
- 通过 Hook/MCP 连接到 Node Runtime

**启动方式**：
```bash
ccm chat worker  # CLI 启动 Claude Code 进程
```

**实现**：外部 `claude` 进程 + `InteractiveAgentProxy`

---

## 4. Session 层概念

### 4.1 Session（会话）

**定义**：Claude 的对话上下文，包含消息历史和系统提示词。

**关键特性**：
- 有唯一的 `session_id`
- 有消息历史（Message History）
- 有系统提示词（System Prompt）
- 可以调用工具（Tools）

**类型**：

#### 4.1.1 Backend Session（后台会话）

**定义**：在 Node Runtime 内部运行的会话，使用 claude-agent-sdk 创建。

**特点**：
- 轻量级，适合大量并发
- 由 Node Runtime 管理生命周期
- 根据 session_scope 自动创建和销毁

**实现**：
```python
class BackendSession:
    session_id: str
    type: Literal["backend"]
    agent_session: AgentSession  # claude-agent-sdk
    pending_events_count: int
```

#### 4.1.2 Interactive Session（交互式会话）

**定义**：在独立 Claude Code 进程中运行的会话，用户可以直接交互。

**特点**：
- 有独立的进程
- 用户可以看到和干预
- 可以"占据"某个 session_id

**实现**：外部 Claude Code 进程 + `InteractiveAgentProxy`

---

### 4.2 Session ID（会话标识）

**定义**：会话的唯一标识符，用于事件路由。

**生成规则**：

| session_scope | session_id 格式 | 示例 |
|--------------|-----------------|------|
| `per-event` | `event_id` | `evt-abc123` |
| `upstream-session` | `{upstream_node}:{upstream_session_id}` | `worker:sess-123` |
| `upstream-node` | `node:{upstream_node}` | `node:worker` |
| `global` | `global:global` | `global:global` |
| `global:<name>` | `global:{name}` | `global:ops-bridge` |
| 派发型（自动创建） | `auto-{random}` | `auto-xf7k9` |

---

### 4.3 Session Scope（会话作用域）

**定义**：订阅关系中声明的会话组织策略，决定下游如何创建和复用会话。

**分类**：

#### 创建型策略（Creation Strategy）

根据事件属性计算会话标识，总是创建或复用特定的会话。

| 策略 | 含义 |
|------|------|
| `upstream-session` | 跟随上游会话 |
| `per-event` | 每个事件一个新会话 |
| `upstream-node` | 每个上游节点一个会话 |
| `global[:<name>]` | 全局共享会话 |

#### 派发型策略（Dispatch Strategy）

从节点已有的会话中选择一个来处理事件。

| 策略 | 含义 |
|------|------|
| `random` | 随机选择 |
| `round-robin` | 轮询选择 |
| `load-balanced` | 负载均衡 |
| `sticky-source` | 粘性源（同一上游总是派发到同一会话） |

---

### 4.4 Session Filter（会话过滤器）

**定义**：控制哪些类型的会话参与事件处理（仅对派发型策略有效）。

| Filter | 含义 |
|--------|------|
| `any` | 所有会话 |
| `backend-only` | 仅后台会话 |
| `interactive-only` | 仅交互式会话 |
| `interactive-first` | 优先交互式，无则后台 |

---

## 5. 事件系统概念

### 5.1 Node（节点）

**定义**：事件系统中的基本单元，能够产生和消费事件。

**关键特性**：
- 有唯一标识：`node_id`（在 Mesh 内唯一）
- 有类型：`node_type`（如 `cc`, `scheduler`, `webhook`）
- 能产生事件（Event Producer）
- 能消费事件（Event Consumer，通过订阅）
- 可被订阅（Observable）

**实现对应关系**：
- 逻辑概念：Node
- 进程实体：Node Runtime Process
- 会话实现：Backend Session + Interactive Agent

---

### 5.2 Event（事件）

**定义**：节点间传递的消息，是整个系统的驱动力。

**基本结构**：
```python
class MeshEvent:
    event_id: str                      # 唯一标识
    source_id: str                     # 发送者节点 ID
    target_id: str                     # 接收者节点 ID
    timestamp: datetime
    type: str                          # 事件类型
    session_trace: SessionTrace        # 会话溯源信息
```

**主要类型**：

#### Hook 事件

| 类型 | 触发时机 | 典型用途 |
|------|---------|---------|
| `PreToolUse` | 工具调用前 | 审计、权限控制 |
| `PostToolUse` | 工具调用后 | 日志记录、结果验证 |
| `UserPromptSubmit` | 用户提交输入 | 监控用户意图 |
| `SessionStart` | 会话开始 | 初始化 |
| `SessionEnd` | 会话结束 | 清理 |

#### 通信事件

| 类型 | 用途 |
|------|------|
| `NodeMessage` | 节点间通信、回复阻塞事件 |

---

### 5.3 Session Trace（会话溯源）

**定义**：事件中携带的上游会话信息，提供事件的上下文来源。

**结构**：
```python
class SessionTrace:
    node_id: str                # 产生事件的节点 ID
    upstream_session_id: str    # 上游会话标识
    event_seq: int              # 该会话中的第几个事件
```

**作用**：
- 提供事件的上下文来源
- 为下游的会话对齐策略提供依据
- 不决定下游如何处理（由 session_scope 决定）

---

### 5.4 Subscription（订阅关系）

**定义**：节点间的事件流向定义，形成 Mesh 拓扑。

**关键字段**：
```python
class Subscription:
    source_id: str          # 订阅者（下游）
    target_id: str          # 被订阅者（上游）
    event_pattern: str      # 事件模式（支持 !EventName 表示阻塞）
    session_scope: str      # 会话作用域策略
    session_filter: str     # 会话过滤器
    session_profile: str    # 会话配置文件
```

**事件模式**：

| 模式 | 含义 | 是否阻塞 |
|------|------|---------|
| `*` | 所有事件 | 否 |
| `EventA,EventB` | 特定事件列表 | 否 |
| `!EventA` | 阻塞订阅 | 是 |

**阻塞订阅**：
- 发送方必须等待订阅者回复
- 回复影响发送方的行为
- 用于审计、权限控制等场景
- 多订阅者采用"一票否决制"

---

### 5.5 Event Envelope（事件信封）

**定义**：事件的包装器，携带 ACK/NACK 方法，用于确认事件处理结果。

**结构**：
```python
class EventEnvelope:
    event: MeshEvent
    
    async def ack():
        """确认事件已处理"""
    
    async def nack(requeue: bool):
        """拒绝事件，可选择是否重新入队"""
```

**作用**：
- 实现 At-least-once 语义
- 支持事件重试
- 提供幂等性保证的基础

---

## 6. 抽象接口概念

### 6.1 MeshClient

**定义**：节点运行时的事件系统接口，每个 Node Runtime Process 持有一个。

**组成**：
```python
class MeshClient:
    mesh_id: str
    node_id: str
    inbox: MeshInbox
    outbox: MeshOutbox
    context: MeshContext
```

---

### 6.2 MeshInbox

**定义**：节点的事件接收接口，提供异步迭代器来消费事件。

**关键方法**：
```python
class MeshInbox:
    async def __aiter__() -> AsyncIterator[EventEnvelope]:
        """异步迭代所有待处理事件"""
    
    async def ack(event: MeshEvent):
        """确认事件处理完成"""
```

---

### 6.3 MeshOutbox

**定义**：节点的事件发送接口，提供发送和回复方法。

**关键方法**：
```python
class MeshOutbox:
    async def send(event: MeshEvent):
        """发送非阻塞事件"""
    
    async def send_blocking(event: MeshEvent, timeout: float) -> List[Any]:
        """发送阻塞事件，等待回复"""
    
    async def reply(event_id: str, content: Any):
        """回复事件"""
```

---

### 6.4 MeshAdmin

**定义**：控制平面接口，用于管理节点和订阅关系。

**关键方法**：
```python
class MeshAdmin:
    async def create_node(node_id: str, config: dict):
        """创建节点"""
    
    async def subscribe(subscription: Subscription):
        """创建订阅关系"""
    
    async def register_node_capabilities(node_id: str, capabilities: dict):
        """注册节点能力"""
```

---

### 6.5 MeshContext

**定义**：上下文平面接口，提供拓扑和语义信息。

**关键方法**：
```python
class MeshContext:
    def get_topology_context(node_id: str) -> TopologyContext:
        """获取节点的拓扑上下文（订阅关系）"""
    
    def get_event_semantics(event_type: str) -> EventSemantics:
        """获取事件类型的语义信息"""
```

---

## 7. 组件概念

### 7.1 SessionResolver

**定义**：统一的会话解析器，根据 session_scope 和 session_trace 决定事件应该路由到哪个会话。

**职责**：
1. 判断是创建型还是派发型策略
2. 计算或选择目标 session_id
3. 获取或创建对应的会话

---

### 7.2 SessionManager

**定义**：会话管理器，管理节点内的所有 Backend Session 和 Interactive Agent。

**职责**：
1. 创建和销毁 Backend Session
2. 注册和管理 Interactive Agent
3. 提供统一的会话查询接口
4. 自动清理不活跃会话

---

### 7.3 EventProcessor

**定义**：事件处理器，将接收到的事件分发到正确的会话。

**职责**：
1. 使用 SessionResolver 解析目标会话
2. 将事件格式化为消息
3. 投递消息到会话
4. 处理 ACK/NACK

---

### 7.4 HookHandler

**定义**：Hook 事件处理器，捕获 Claude Code 的 Hook 并转换为 Mesh 事件。

**职责**：
1. 注册 Hook 回调
2. 创建 MeshEvent
3. 判断是否阻塞订阅
4. 发送事件并等待回复（如果阻塞）
5. 聚合多订阅者的回复

---

### 7.5 WaiterRegistry

**定义**：全局等待点注册表，管理阻塞事件的等待-唤醒机制。

**职责**：
1. 注册 EventWaiter
2. 触发等待点（收到回复时）
3. 清理超时的等待点

---

## 8. 用户交互概念

### 8.1 User Session（用户会话）

**定义**：用户通过终端与某个 Agent Process 的交互会话。

**特点**：
- 有 PTY/TTY 连接
- 用户可以 attach/detach
- 生命周期由用户控制

**启动方式**：
```bash
ccm chat worker    # 创建新的用户会话
```

---

### 8.2 Program Mode（编程模式）

**定义**：节点的"离线培训模式"，用于配置节点的角色和行为。

**特点**：
- 断开 Mesh 连接（不收发事件）
- 用户与节点对话，配置职责和规则
- 知识持久化到 CLAUDE.md 或 MCP memory

**启动方式**：
```bash
ccm program auditor
```

---

### 8.3 Interactive Mode（交互模式）

**定义**：节点的前端模式，用户可以直接交互。

**特点**：
- 连接到 Mesh（可以收发事件）
- 用户可以看到和参与事件处理
- 产生的事件会发送到订阅者

**启动方式**：
```bash
ccm run worker
```

---

### 8.4 Background Mode（后台模式）

**定义**：节点的后台模式，自动处理事件，无用户交互。

**特点**：
- 完全自动化
- 由 Backend Conversation 实现
- 根据 session_scope 自动创建会话

**启动方式**：
- 自动启动（Interactive 节点启动时）
- 手动启动：`ccm start logger`

---

## 9. 数据概念

### 9.1 Mosaic Database（Mosaic 数据库）

**定义**：存储所有 Mesh 实例数据的统一 SQLite 数据库。

**位置**：`~/.mosaic/mosaic.db`

**表结构**：
- `meshes`：Mesh 实例定义
- `nodes`：节点定义（包含 `mesh_id` 字段）
- `subscriptions`：订阅关系（包含 `mesh_id` 字段）
- `event_queue`：事件队列（包含 `mesh_id` 字段）
- `processed_events`：已处理事件（可选，用于幂等性，包含 `mesh_id` 字段）

**数据隔离**：
- 所有表包含 `mesh_id` 字段
- 查询时通过 `WHERE mesh_id = ?` 过滤
- 索引包含 `mesh_id` 以优化查询性能

**Schema 示例**：
```sql
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    mesh_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    workspace TEXT,
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mesh_id, node_id)
);

CREATE INDEX idx_nodes_mesh ON nodes(mesh_id);
```

---

### 9.2 Session Profile（会话配置）

**定义**：会话的配置模板，定义系统提示词、工具、超时等参数。

**结构**：
```python
class SessionProfile:
    name: str
    system_prompt: str
    tools: List[str]
    ttl: int                    # 会话生存时间（秒）
    max_messages: int           # 最大消息数
```

**使用**：
```bash
ccm sub auditor worker "!PreToolUse" --session-profile auditor-strict
```

---

## 10. 层次关系图

```
┌─────────────────────────────────────────────────────────┐
│ Mosaic (系统)                                           │
│  └─ Mesh Instance (实例)                                │
│      ├─ Mosaic Daemon Process (守护进程)                │
│      │                                                   │
│      └─ Mesh Topology (拓扑)                            │
│          ├─ Node (节点)                                  │
│          │   └─ Node Runtime Process (节点进程)          │
│          │       ├─ Backend Session (后台会话)          │
│          │       │   └─ Session (会话)                  │
│          │       │                                      │
│          │       └─ Interactive Agent Proxy (代理)      │
│          │           └─ Interactive Agent Process       │
│          │               └─ Session (会话)              │
│          │                                              │
│          ├─ Event (事件)                                │
│          │   ├─ Hook Event                             │
│          │   └─ NodeMessage                            │
│          │                                              │
│          └─ Subscription (订阅关系)                     │
│              ├─ Event Pattern                          │
│              ├─ Session Scope                          │
│              └─ Session Filter                         │
└─────────────────────────────────────────────────────────┘
```

---

## 11. 术语对照表

### 11.1 中英文对照

| 中文 | 英文 | 缩写 |
|------|------|------|
| Mosaic 系统 | Mosaic System | - |
| Mesh 实例 | Mesh Instance | - |
| Mesh 拓扑 | Mesh Topology | - |
| Daemon 进程 | Mosaic Daemon Process | Daemon |
| 节点 | Node | - |
| 节点运行时进程 | Node Runtime Process | Runtime |
| 智能体进程 | Agent Process | Agent |
| 后台会话 | Backend Session | - |
| 交互式智能体 | Interactive Agent | - |
| 会话 | Session | - |
| 会话标识 | Session ID | session_id |
| 会话作用域 | Session Scope | - |
| 会话过滤器 | Session Filter | - |
| 会话配置 | Session Profile | - |
| 事件 | Event | - |
| 事件信封 | Event Envelope | - |
| 会话溯源 | Session Trace | - |
| 订阅关系 | Subscription | Sub |
| 事件模式 | Event Pattern | - |
| Hook 事件 | Hook Event | - |
| 用户会话 | User Session | - |

### 11.2 关键缩写

| 缩写 | 全称 |
|------|------|
| CC | Claude Code |
| MCP | Model Context Protocol |
| IPC | Inter-Process Communication |
| PTY | Pseudo-TTY |
| UDS | Unix Domain Socket |
| ACK | Acknowledge（确认） |
| NACK | Negative Acknowledge（拒绝） |
| TTL | Time To Live（生存时间） |

---

## 12. 常见混淆辨析

### 12.1 Node vs Node Runtime Process

| 概念 | 层级 | 含义 |
|------|------|------|
| Node | 逻辑概念 | 事件系统中的基本单元 |
| Node Runtime Process | 进程实体 | 实现 Node 的运行时进程 |

**关系**：Node 是抽象概念，Node Runtime Process 是具体实现。

---

### 12.2 Agent Process vs Backend Session

| 概念 | 进程 | 适用场景 |
|------|------|---------|
| Agent Process (Interactive) | 独立进程 | 用户交互、长期会话 |
| Backend Session | 非独立进程 | 自动化任务、高并发 |

**关系**：两者都是"会话"的实现方式，但进程模型不同。

---

### 12.3 session_id vs upstream_session_id

| 术语 | 含义 |
|------|------|
| `session_id` | 下游节点用于路由的会话标识 |
| `upstream_session_id` | 上游节点的会话标识（在 session_trace 中） |

**关系**：
- `upstream_session_id` 是上游的事实
- `session_id` 是下游根据 `session_scope` 计算出的路由目标

---

## 13. 使用指南

### 13.1 创建节点

```bash
# 创建 CC 节点
ccm create worker --path ./worker --type cc

# 配置重启策略
ccm config worker set restart-policy always
ccm config worker set max-retries 5
```

### 13.2 建立订阅

```bash
# 阻塞订阅（审计）
ccm sub auditor worker "!PreToolUse" \
    --session-scope upstream-session

# 非阻塞订阅（日志）
ccm sub logger worker "*" \
    --session-scope round-robin \
    --session-filter backend-only
```

### 13.3 节点生命周期

```bash
# 启动 Daemon
ccm daemon start

# 交互模式（前端）
ccm run worker

# 后台模式
ccm start logger

# 编程模式（培训）
ccm program auditor

# 查看状态
ccm ps
ccm status worker
```

---

## 14. 总结

### 14.1 核心层次

```
系统层：Mosaic → Mesh Instance
进程层：Daemon → Node Runtime → Agent
Session 层：Session (Backend / Interactive)
事件层：Event → Subscription → Session Trace
```

### 14.2 关键设计原则

1. **一节点一运行时进程**：Node Runtime Process 代表节点
2. **会话与进程解耦**：Backend Conversation 不需要独立进程
3. **事件驱动**：所有节点通过事件通信
4. **订阅关系决定行为**：session_scope 决定会话组织方式
5. **抽象分层**：清晰的接口层次（MeshClient/Inbox/Outbox）

---

**文档结束**

_本文档将随着系统演进持续更新。如有歧义或遗漏，请提 Issue。_

