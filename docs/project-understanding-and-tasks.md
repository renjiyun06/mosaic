# Mosaic (原 Claude Code Mesh) - 项目理解与工作文档

> **文档用途**: 作为 AI 助手的记忆来源，用于下一个会话快速恢复上下文  
> **创建日期**: 2025-11-23  
> **最后更新**: 2025-11-24  
> **会话主题**: CC 节点与事件系统集成设计

---

## 0. 最新结论速览（2025-11-24 当前会话）

### 本次会话重点（第二次）：崩溃恢复、会话管理、术语统一

1. **崩溃恢复机制已设计**：
   - **Daemon 可靠性**：systemd 管理 + 开发环境自动恢复
   - **Node Runtime 监控**：PID 检测 + 可选心跳 + 指数退避重启
   - **事件投递保证**：At-least-once 语义 + 恢复窗口机制（默认 5 分钟）
   - **会话恢复**：Backend Session 按需重建，Interactive Agent 自动重连

2. **Session Scope 策略体系扩展**：
   - **创建型策略**：upstream-session, per-event, upstream-node, global（已有）
   - **派发型策略**：random, round-robin, load-balanced, sticky-source（新增）
   - **Session Filter**：backend-only, interactive-only, interactive-first（新增）
   - 解决了多会话并发处理和负载均衡问题

3. **Backend Session vs Interactive Agent 澄清**：
   - **Backend Session**：在 Node Runtime 内部（claude-agent-sdk），轻量级，适合高并发
   - **Interactive Agent**：独立 Claude Code 进程，通过 IPC 协作（非父子关系）
   - Agent Process 不一定是 Node Runtime 的子进程
   - 路由优先级：Interactive Agent → Backend Session

4. **术语统一为 Session**：
   - **SessionTrace**（原 ConversationTrace）：事件溯源信息
   - **Backend Session**（原 Backend Conversation）：后台会话
   - **SessionManager**（原 ConversationManager）：会话管理器
   - `session_id` 用于路由，`upstream_session_id` 在 SessionTrace 中

5. **数据库架构调整**：
   - 从"每个 Mesh 独立数据库"改为"统一数据库 + mesh_id 区分"
   - `~/.mosaic/mosaic.db`：统一数据库
   - `~/.mosaic/<mesh_id>/`：运行时目录（Socket、日志、PID）

6. **文档产出**：
   - `docs/architecture/cc-node-event-integration.md`：更新了 Session Scope 策略、Backend Session 说明
   - `docs/architecture/crash-recovery.md`：完整的崩溃恢复设计
   - `docs/architecture/concepts-glossary.md`：所有核心概念的术语词汇表

---

## 0.05 本次会话（第一次）的重点回顾

1. **会话对齐机制已明确**：
   - **SessionTrace**：事件携带上游会话溯源信息（`node_id`, `upstream_session_id`, `event_seq`）
   - **Session Scope**：订阅关系中声明下游会话组织策略
   - 会话对齐由**订阅关系**决定，而非事件发送方

2. **阻塞事件的等待-唤醒机制已设计**：
   - **EventWaiter**：抽象的等待点，解耦业务逻辑与阻塞细节
   - **WaiterRegistry**：全局注册表，管理所有等待点
   - 高层代码（Hook/会话）无需关心具体阻塞机制，统一使用 `send_blocking()` 接口

3. **PreToolUse 阻塞语义已澄清**：
   - PreToolUse 是否阻塞取决于订阅关系（`!PreToolUse` vs `PreToolUse`），而非事件类型
   - 阻塞订阅的回复必须返回到 Hook 流程，才能真正影响工具调用
   - 审计节点可以在自己的会话中用 Claude 做决策，但回复通过 `reply()` 返回到 Hook

---

## 0.1 历史结论速览（2025-11-23 会话）

1. **项目定名为 Mosaic**：`cc-mesh` 只是旧称。Mosaic 面向任何智能体（Claude、Gemini、其他框架）与系统组件（Scheduler/Webhook 等）的协作网格。
2. **事件系统抽象层确定**：
   - **MeshClient**：每个节点进程持有，包含 `mesh_id` / `node_id` / `inbox` / `outbox` / `context`。
   - **MeshInbox**：异步迭代器 + `EventEnvelope`（携带 `ack/nack`），落地“一个节点一个进程，对内任意会话策略”。
   - **MeshOutbox**：`send` + `reply`，语义为 Fire-and-Persistence；发送端负责分发。
   - **MeshAdmin**（控制平面）：用于 `create_node`、`subscribe`，并新增 **能力注册**（Produced/Consumed Events + 语义）。
   - **MeshContext**（上下文平面）：节点可查询自身“拓扑事实 + 事件语义”，供 Runtime 注入 System Prompt。事件系统不负责角色描述，那是 Programming 阶段的内容。
3. **多 Mesh 隔离**：每个 Mesh 有独立的根目录 `~/.mosaic/<mesh_id>/`，内含 `mesh.db`、`sockets/` 等。`node_id` 只在同一 Mesh 内唯一。
4. **节点与会话的关系**：事件系统只要求“一节点一进程”；节点内部可以使用单会话、事件会话、会话池等策略。对 CLI 场景需通过 PTY Wrapper 管理 I/O，使 Mesh 事件像“系统消息”注入现有会话。
5. **文档状态**：`docs/architecture/event-system-spec.md` (v1.4) 已全面描述上述抽象层，将作为后续代码重构的蓝本。

---

## 1. 项目功能和概念详解

### 1.1 项目愿景

**Mosaic**（原 Claude Code Mesh，简称 CCM）是一个面向多智能体与系统组件的事件驱动网格基础设施。它不再局限于 Claude Code（CC）实例，后续可以并列接入 Gemini、LangChain/AutoGen Agent、调度器、Webhook 等组件，只要它们能遵守 Mesh 的事件契约即可。

**核心价值（更新）**：
- 🔍 **多智能体监督**：让一个智能体审阅另一个智能体的行为
- 🤝 **异构协作**：Claude/Gemini/系统组件可在同一 Mesh 中协同
- 📊 **事件追踪**：事件全量持久化，便于审计、回放
- 🎯 **灵活编排**：通过订阅关系和语义契约快速组合不同拓扑
- 🧠 **LLM-Native 语义注入**：事件自带语义描述，可直接喂给智能体

---

### 1.2 核心概念

#### **概念 1: Node (节点)** ⭐⭐⭐

**定义**：节点是系统的基本单元，具有以下特征：
- 有唯一标识 (node_id)
- 能产生事件 (Event Producer)
- 能被订阅 (Observable)
- (可选) 能消费事件 (Event Consumer)

**节点类型**（泛化概念）：
```
Node (抽象)
├─ CC Node (当前实现重点)
│  - Claude Code 实例
│  - 必须有工作区 (workspace)
│  - 产生 Hook 事件
│  - 消费其他节点事件
│
├─ Scheduler Node (未来扩展)
│  - 调度系统
│  - 产生定时事件
│
├─ Webhook Node (未来扩展)
│  - HTTP 服务
│  - 桥接外部系统
│
└─ 其他类型节点...
```

**CC 节点的四种状态**：

| 状态 | 含义 | 触发方式 | 用途 |
|------|------|---------|------|
| **idle** | 空闲 | 初始状态 | 节点未运行 |
| **program** | 编程模式 | `ccm program NODE_ID` | 配置节点职责和行为 |
| **interactive** | 交互模式 | `ccm run NODE_ID` | 用户直接操作的前端 CC |
| **background** | 后台模式 | 自动启动 | 监听和响应事件 |

**重要约束**：
- ✅ **一节点一进程**：每个节点在同一时间只能有一个运行中的 CC 实例
- ✅ **状态互斥**：节点在同一时间只能处于一个状态
- ✅ **工作区绑定**：CC 节点必须有工作区（Claude Code 自身的概念）

---

### 1.3 最新：事件系统抽象层（Mosaic Spec v1.4）

为了解耦“节点实现”与“事件基础设施”，当前会话产出了 `docs/architecture/event-system-spec.md`，主要结论：

| 平面 | 核心对象 | 职责 | 关键说明 |
|------|----------|------|----------|
| 数据平面 | `MeshClient` | 节点运行时接口，包含 `mesh_id`/`node_id`/`inbox`/`outbox`/`context` | 一节点一进程；同一个节点在不同 Mesh 需要不同进程 |
| 输入 | `MeshInbox` + `EventEnvelope` | 异步迭代器；`ack/nack` 明确 At-least-once 语义 | 节点内部的会话策略（单会话/事件会话）由 Runtime 决定 |
| 输出 | `MeshOutbox` | `send`（Fire-and-Persistence）与 `reply` | 发送端负责分发（Sender-side Dispatch） |
| 控制平面 | `MeshAdmin` | `create_node`、`subscribe`、`register_node_capabilities` | 能力注册需声明 **产生/消费** 的事件及语义 |
| 上下文平面 | `MeshContext` | `get_topology_context`、`get_event_semantics` | 提供“我订阅谁/谁订阅我”与事件语义，供 Runtime 注入 Prompt |

其他要点：
- **多 Mesh 隔离**：约定目录 `~/.mosaic/<mesh_id>/`（内含 `mesh.db`、`sockets/` 等），`node_id` 只在 Mesh 内唯一。
- **事件语义声明**：每种事件需提供自然语言描述和 Schema，以便智能体理解。
- **角色信息不在事件系统中定义**：事件系统只提供客观事实；节点的“角色/职责”由 Program 模式注入。

---

#### **概念 2: Event (事件)** ⭐⭐⭐

**定义**：事件是节点间传递的消息，是整个系统的驱动力。

**事件来源**：

1. **Claude Code Hook 机制**（主要来源）
   - 参考：https://code.claude.com/docs/en/hooks
   - Hook 类型：
     - `PreToolUse` - 工具使用前
     - `PostToolUse` - 工具使用后
     - `UserPromptSubmit` - 用户提交提示词
     - `SessionStart` / `SessionEnd` - 会话开始/结束
     - `Stop` - 停止信号
     - `PermissionRequest` - 权限请求
     - `Notification` - 通知

2. **节点间通信**
   - `NodeMessage` - 节点主动发送的消息或对事件的回复

3. **未来扩展**
   - 定时调度事件
   - 系统组件事件
   - 自定义事件类型

**事件基本结构**：
```python
class MeshEvent:
    event_id: str        # 唯一标识
    source_id: str       # 发送者节点 ID
    target_id: str       # 接收者节点 ID
    timestamp: datetime
    type: str           # 事件类型
```

**事件序列化**：使用 XML 格式（未来可能改为 JSON）

**关键特性**：
- ✅ 事件通过 **SQLite 数据库 + Unix Domain Socket** 传递
- ✅ 事件持久化在数据库中（审计、容错）
- ⚠️ 事件生命周期管理尚未完全实现

---

#### **概念 3: Subscription (订阅关系)** ⭐⭐⭐

**定义**：订阅定义了节点间的事件流向，形成网格拓扑。

**订阅关系**：
```
ccm sub SOURCE_ID TARGET_ID EVENT_PATTERN
```
- **SOURCE**: 订阅者（接收事件的节点）
- **TARGET**: 被订阅者（产生事件的节点）
- **EVENT_PATTERN**: 事件模式

**事件模式语法**：

| 模式 | 含义 | 示例 |
|------|------|------|
| `*` | 所有事件（非阻塞） | `ccm sub logger worker "*"` |
| `EventA,EventB` | 特定事件（非阻塞） | `ccm sub monitor worker "PreToolUse,PostToolUse"` |
| `!EventA` | 阻塞订阅 | `ccm sub auditor worker "!PreToolUse"` |

**阻塞 vs 非阻塞**：

##### **阻塞订阅** (`!EventName`)
- TARGET 发出事件后，**必须等待** SOURCE 响应
- 用于需要授权、审查的场景
- 响应影响 TARGET 的后续行为

**多个阻塞订阅者的聚合规则**：
```
规则: 一票否决制
- 任何一个订阅者回复 "deny" → 最终拒绝
- 任何一个订阅者回复 "ask" → 最终询问
- 所有订阅者回复 "allow" → 最终允许
- 超时视为 "deny"（带超时提示，以便重试）
- 拒绝理由/询问提示会被汇总
```

**示例**：
```bash
ccm sub auditor-1 worker "!PreToolUse"
ccm sub auditor-2 worker "!PreToolUse"

# worker 准备使用工具
# → 同时发送给 auditor-1 和 auditor-2
# → 等待两者响应
# → auditor-1: allow, auditor-2: deny
# → 最终结果: deny (汇总理由)
```

##### **非阻塞订阅** (`EventName` 或 `*`)
- TARGET 发出事件后，**立即继续**，不等待响应
- 用于日志、监控、通知等场景

**主要用途**：
1. **日志记录**：logger 节点记录所有事件
2. **监控告警**：monitor 节点分析事件模式
3. **上下文增强**（待讨论）：订阅者提供额外上下文

**上下文增强的困境** ⚠️：
- 如果非阻塞，TARGET 已经继续执行了
- 如何让 TARGET "收到"订阅者提供的上下文？
- 可能需要"短暂等待窗口"机制

---

#### **概念 4: Program 模式** ⭐⭐⭐

**定义**：Program 模式是一种"离线培训模式"，用户通过对话配置节点的职责和行为。

**不是传统意义的"编程"**，而是**对话式配置 / AI 培训**。

**Program 模式的特点**：
```
✓ 断开 Mesh 连接
  - 不触发 Mesh 事件
  - 不能使用 Mesh 相关的 MCP 工具
  
✓ 节点仍然"知道"自己的位置
  - 通过系统提示词告知网络拓扑
  - 知道自己订阅了谁、被谁订阅
  
✓ 用户与 CC 对话
  - 告知节点在网络中的角色
  - 对齐职责和工作流程
  - 演练场景和决策逻辑
  
✓ 知识持久化（由用户决定）
  - CLAUDE.md 文件（CC 自带的记忆机制）
  - MCP memory 服务器（外置记忆）
  - 其他持久化方式
```

**典型流程**：
```bash
# 1. 创建节点
ccm create supervisor --path ./supervisor

# 2. 编程节点（培训）
ccm program supervisor

# 系统启动 CC 交互界面，注入系统提示词：
#   "你是 Mesh 网络中的 supervisor 节点。
#    你订阅了 worker 节点的 PreToolUse 事件（阻塞）。
#    当收到事件时，你应该使用 respond_to_pre_tool_use 工具响应。
#    现在请告诉我你的职责和工作方式。"

# 用户与 CC 对话：
User: "你的职责是审查 worker 的所有工具使用。
       如果是删除操作，特别小心。
       如果删除的是重要文件，拒绝。
       你理解了吗？"

Claude: "理解。我会仔细审查每个工具调用..."

# 用户可以演练场景，让 Claude 内化规则

# 3. 持久化（用户操作）
User: "请将你的职责和规则写入 CLAUDE.md 文件"
# 或使用 MCP memory 工具

# 4. 实际运行
ccm run worker  # supervisor 自动启动为后台
```

**Program 模式与其他模式的关系**：
```
program → 配置阶段
   ↓
  idle
   ↓
interactive/background → 运行阶段（加载 program 时的配置）
```

---

#### **概念 5: 系统使用流程** ⭐⭐

**三阶段流程**：

```
┌─────────────────────────────────────┐
│  阶段 1: 系统构建 (Structure)        │
│  - 创建节点                          │
│  - 建立订阅关系                      │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│  阶段 2: 节点编程 (Programming)      │
│  - 配置每个节点的角色                │
│  - 对齐工作方式和决策逻辑            │
│  - 持久化配置                        │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│  阶段 3: 实际运行 (Operation)        │
│  - 启动前端 CC（用户交互）           │
│  - 自动启动后台 CC（处理事件）       │
│  - 完成实际任务                      │
└─────────────────────────────────────┘
```

**示例**：
```bash
# === 阶段 1: 构建 ===
ccm init
ccm create worker --path ./worker
ccm create supervisor --path ./supervisor
ccm sub supervisor worker "!PreToolUse"

# === 阶段 2: 编程 ===
ccm program supervisor
# 用户培训 supervisor 的审查逻辑

ccm program worker
# 用户培训 worker 的工作方式

# === 阶段 3: 运行 ===
ccm run worker
# - worker 启动为前端 CC
# - supervisor 自动启动为后台 CC
# - 用户与 worker 交互，supervisor 监督
```

---

#### **概念 6: 后台 CC 的工作机制** ⭐⭐⭐

**当前设计思路**：

```python
# 前端 CC 启动
ccm run worker

→ ClaudeCode.run_interactive():
  1. 检查 worker 状态（必须是 idle）
  2. 更新 worker 状态为 interactive
  3. 查询订阅链：找到所有订阅 worker 的节点
  4. 启动所有订阅者为后台 CC
     └→ subprocess.Popen([runtime.py, --node-id, "supervisor"])
  5. 启动 worker 的前台 Claude Code 进程
  6. 等待前台进程结束
  7. 清理：关闭所有后台进程，恢复状态
```

**后台 CC 的运行循环**：
```python
# runtime.py: run_background()
async def run_background(self):
    # 1. 创建 Inbox (监控数据库)
    inbox = Inbox(self.node_id)
    await inbox.start()
    
    # 2. 创建 Claude Agent (通过 claude-agent-sdk)
    agent = Agent(...)
    session = agent.create_session()
    
    # 3. 加载系统提示词
    system_prompt = generate_system_prompt(self.node_id)
    # 包含：
    # - Mesh 网络拓扑信息
    # - 节点的订阅关系
    # - Program 阶段的培训内容（从 CLAUDE.md 或 memory 加载）
    
    session.set_system_prompt(system_prompt)
    
    # 4. 持续会话循环
    async for event in inbox:
        # 将事件投递到会话
        message = f"New event received: {event.to_json()}"
        response = await session.send_message(message)
        
        # Claude 自动调用 MCP 工具响应
        # 如: respond_to_pre_tool_use(event_id, decision, reason)
```

**Inbox 的工作原理**：
```python
class Inbox:
    """监控数据库，获取待处理事件"""
    
    async def __anext__(self):
        while True:
            # 1. 查询数据库
            event = await EventRepository.fetch_one_pending(self.node_id)
            if event:
                return event
            
            # 2. 如果没有事件，等待信号
            await self.signal_listener.wait_for_signal()
            # (UDS 收到唤醒信号，重新查询)
```

**MCP 工具提供响应能力**：
```python
# integration/mcp.py
@mcp.tool()
async def respond_to_pre_tool_use(
    event_id: str,
    permission_decision: Literal["allow", "deny", "ask"],
    permission_decision_reason: str = None
):
    # 创建回复消息
    node_message = NodeMessage(
        source_id=current_node_id,
        target_id=event_source_id,
        reply_to=event_id,
        content={
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": permission_decision,
                "permissionDecisionReason": permission_decision_reason
            }
        }
    )
    
    # 发送回复
    await Outbox.send(target_id, node_message)
```

---

#### **概念 7: 消息传递机制** ⭐⭐

**架构**：SQLite + Unix Domain Socket

```
Sender Node                    Database                 Receiver Node
     │                            │                           │
     ├─1. Create Event            │                           │
     │                            │                           │
     ├─2. Save to DB ─────────────┤                           │
     │   (event_queue table)      │                           │
     │                            │                           │
     ├─3. Send Signal (UDS) ───────────────────────────────────┤
     │   (send byte to socket)    │                           │
     │                            │                           │
     │                            │   ┌───────────────────────┤
     │                            │   │ 4. Receive Signal     │
     │                            │   │    (UDS listener)     │
     │                            │   │                       │
     │                            │   │ 5. Query DB ──────────┤
     │                            │   │    (fetch pending)    │
     │                            ├───┘                       │
     │                            │                           │
     │                            │                  6. Process Event
     │                            │                           │
     │                            │   ┌───────────────────────┤
     │   ┌────────────────────────┼───┘ 7. Send Reply        │
     │   │                        │     (optional)            │
     ├───┤ 8. Receive Reply       │                           │
     │                            │                           │
```

**Unix Domain Socket**：
- 路径：`~/.cc-mesh/sockets/{node_id}.sock`
- 协议：发送单字节 `b'1'` 作为唤醒信号
- 异步 IO：使用 `asyncio.start_unix_server`

**数据库（SQLite WAL 模式）**：
- 支持并发读写
- 事件持久化
- 可审计、可恢复

---

### 1.3 技术栈

- **Python 3.13+**
- **SQLite (WAL mode)**: 数据存储
- **Unix Domain Socket**: 进程间信号通知
- **claude-agent-sdk**: 后台 CC 实现
- **MCP (Model Context Protocol)**: CC 工具集成
- **Pydantic**: 数据验证
- **Click + Rich**: CLI 界面

---

## 2. 当前实现情况

### 2.1 已实现的功能 ✅

#### **数据层**
- ✅ SQLite 数据库初始化 (`init_db`, `reset_db`)
- ✅ 三张表：nodes, subscriptions, event_queue
- ✅ Repository 模式：NodeRepository, SubscriptionRepository, EventRepository

#### **数据模型**
- ✅ Node, Subscription, MeshEvent 基类
- ✅ 事件类型：UserPromptSubmit, NodeMessage, PreToolUse, PostToolUse, SessionStart, SessionEnd, Stop
- ✅ 事件 XML 序列化/反序列化

#### **CLI 命令**
- ✅ `ccm init` - 初始化系统
- ✅ `ccm reset` - 重置系统
- ✅ `ccm create NODE_ID --path PATH` - 创建节点
- ✅ `ccm run NODE_ID` - 运行节点（交互模式）
- ✅ `ccm program NODE_ID` - 编程模式（框架存在但未实现）
- ✅ `ccm sub SOURCE TARGET PATTERN` - 创建订阅
- ✅ `ccm list` - 列出节点和订阅

#### **消息传递**
- ✅ Outbox: send, send_and_wait, batch_send_and_wait
- ✅ Inbox: 基于 UDS 的异步事件接收
- ✅ SignalClient / SignalListener: UDS 信号机制

#### **Hook 集成**
- ✅ HookRunner: Hook 执行引擎（中间件模式）
- ✅ HookContext, HookResult: 上下文和结果对象
- ✅ HookLogHandler: 日志记录 Handler
- ✅ MeshNetworkHandler: 网络传播 Handler（PreToolUse 部分实现）

#### **MCP 集成**
- ✅ MCP Server 基础框架
- ✅ `respond_to_pre_tool_use` 工具（完整实现）

#### **配置安装**
- ✅ `install_settings_json`: 安装 Hook 配置到 `.claude/settings.json`
- ✅ `install_mcp`: 安装 MCP 配置到 `.mcp.json`

---

### 2.2 部分实现 ⚠️

#### **运行时**
- ⚠️ `ClaudeCode.run_interactive()`: 框架存在，但后台节点启动逻辑可能有问题
- ⚠️ `ClaudeCode.run_background()`: 只打印事件，未实现完整的会话循环
- ❌ `ClaudeCode.run_program()`: 完全空实现
- ❌ `ClaudeCode.run()`: 方法不存在（需要添加模式分发）

#### **事件处理**
- ⚠️ MeshNetworkHandler: 只实现了 `handle_pre_tool_use`
- ❌ 其他事件类型（PostToolUse, UserPromptSubmit 等）未实现

#### **MCP 工具**
- ✅ `respond_to_pre_tool_use`: 完整实现
- ❌ 其他工具（respond_to_post_tool_use 等）空实现或占位

#### **事件状态管理**
- ❌ 事件状态转换（pending → processing → completed）未实现
- ❌ 事件获取后未标记为已处理
- ❌ 可能导致重复处理

---

### 2.3 严重问题（Critical Bugs） 🔴

#### **1. 数据模型方法缺失**
```python
# repository.py:18
return Node.from_dict(node)  # ❌ 方法不存在
```
**影响**: 运行时抛出 AttributeError

#### **2. ClaudeCode 未保存 mode**
```python
# runtime.py:14
def __init__(self, node_id: str, mode: ...):
    self.node_id = node_id
    # ❌ 缺少: self.mode = mode
```
**影响**: 无法根据 mode 选择运行方式

#### **3. HookRunner.handlers 初始化错误**
```python
# hook_runner.py:91
self.handlers = None  # ❌ 应该是 []
```
**影响**: add_handler() 调用时抛出 AttributeError

#### **4. ClaudeCode.run() 方法缺失**
```python
# cli/main.py:103
asyncio.run(cc.run())  # ❌ 方法不存在
```
**影响**: 无法启动节点

---

### 2.4 未实现的功能 ❌

- ❌ 节点删除和更新
- ❌ 订阅删除和更新
- ❌ 事件清理策略
- ❌ 错误处理和重试机制
- ❌ 节点健康检查
- ❌ 监控和调试工具
- ❌ 配置管理系统
- ❌ 测试用例
- ❌ 完整的文档和示例

---

## 3. 本次合作重点要解决的问题

### 3.1 核心目标

**本次会话的主要目标**：**对齐项目的概念和功能**，而非立即实施重构。

### 3.2 已完成的工作 ✅

1. **✅ 澄清核心概念**
   - Node (节点) 的泛化概念
   - Event (事件) 的来源和类型
   - Subscription (订阅) 的阻塞/非阻塞语义
   - Program 模式的真实含义
   - 后台 CC 的工作机制

2. **✅ 确定架构原则**
   - 一节点一进程
   - 纯消息通信（不共享状态）
   - 节点状态互斥

3. **✅ 创建文档**
   - `concepts-and-features.md`: 概念和功能详解
   - `architecture.md`: 系统架构设计
   - `refactoring-plan.md`: 重构计划
   - `README.md`: 项目介绍
   - `docs/architecture/event-system-spec.md`（v1.4）: Mosaic 抽象层规范（MeshClient/Inbox/Outbox/Admin/Context）
   - `docs/architecture/cc-node-event-integration.md`（2025-11-24）: CC 节点与事件系统集成设计

### 3.3 本次会话（2025-11-24）已完成 ✅

#### 第一阶段：事件集成设计

1. **✅ 会话对齐机制设计**
   - SessionTrace：事件中的会话溯源信息
   - Session Scope（创建型策略）：订阅关系中的会话作用域声明
   - SessionManager：会话解析与管理

2. **✅ 阻塞事件的等待-唤醒机制**
   - EventWaiter + WaiterRegistry：通用的阻塞抽象
   - 高层代码统一使用 `send_blocking()` 接口
   - 支持多订阅者并发等待和决策聚合

3. **✅ CC 节点事件处理流程**
   - EventProcessor：事件分发
   - HookHandler：Hook 事件处理
   - MCP 工具：回复阻塞事件

#### 第二阶段：崩溃恢复与架构完善

4. **✅ 崩溃恢复机制设计**
   - Daemon 进程的可靠性保障（systemd + 自动恢复）
   - Node Runtime 监控与重启（PID 检测 + 可选心跳 + 指数退避）
   - 事件投递保证（At-least-once 语义 + 恢复窗口机制）
   - 会话恢复策略（Backend Session 按需重建，Interactive Agent 自动重连）

5. **✅ Session Scope 策略体系扩展**
   - 派发型策略：random, round-robin, load-balanced, sticky-source
   - Session Filter：backend-only, interactive-only, interactive-first
   - SessionResolver：统一处理创建型和派发型策略
   - 解决了多会话并发处理和负载均衡问题

6. **✅ Backend Session 与 Interactive Agent 架构澄清**
   - Backend Session：在 Node Runtime 内部（使用 claude-agent-sdk）
   - Interactive Agent：独立 Claude Code 进程，通过 IPC 协作
   - Agent Process 不是 Node Runtime 的子进程，而是协作关系
   - 会话路由优先级：Interactive Agent → Backend Session

7. **✅ 术语统一为 Session**
   - Conversation 系列 → Session 系列
   - SessionTrace, BackendSession, SessionManager
   - session_id（路由目标）vs upstream_session_id（事件溯源）

8. **✅ 数据库架构调整**
   - 从"每个 Mesh 独立数据库"改为"统一数据库 + mesh_id 区分"
   - `~/.mosaic/mosaic.db`：统一数据库
   - `~/.mosaic/<mesh_id>/`：运行时目录（Socket、日志、PID）

9. **✅ 完整文档产出**
   - `cc-node-event-integration.md`：CC 节点与事件系统集成设计（已全面更新）
   - `crash-recovery.md`：崩溃恢复设计（新增）
   - `concepts-glossary.md`：核心概念词汇表（新增）

### 3.4 待明确的设计决策（部分已解决）

#### 已解决 ✅

1. **✅ 节点崩溃处理和监控架构**
   - 已完成设计（见 crash-recovery.md）
   - Daemon + systemd 方案
   - At-least-once 事件投递保证

2. **✅ 后台会话的管理策略**
   - Backend Session：claude-agent-sdk 管理
   - Interactive Agent：独立进程 + IPC
   - 派发型策略解决并发问题

#### 仍需确定 ⚠️

3. **非阻塞订阅的上下文增强机制**
4. **前端 CC 限制是否放宽**
5. **订阅关系是否允许环**

---

## 3.5 本次会话核心设计详解（2025-11-24）

### 3.5.1 会话对齐机制

**核心问题**：当节点 A 订阅节点 B 的事件时，A 用什么粒度来组织会话？

**解决方案**：

1. **ConversationTrace**（事件中携带）：
   ```python
   class ConversationTrace:
       node_id: str        # 产生事件的节点
       session_id: str     # 上游会话标识
       event_seq: int      # 该会话中的第几个事件
   ```

2. **Session Scope**（订阅关系中声明）：
   ```bash
   ccm sub <source> <target> "<pattern>" --session-scope <scope>
   ```
   
   | Scope | 含义 | 会话 Key |
   |-------|------|---------|
   | `upstream-session` | 上游一个会话 → 下游一个会话 | `(upstream_node, session_id)` |
   | `per-event` | 每个事件 → 一个新会话 | `event_id` |
   | `upstream-node` | 上游节点所有会话 → 下游一个会话 | `upstream_node` |
   | `global` | 所有事件 → 同一个长期会话 | `"global"` |

3. **SessionManager**（运行时实现）：
   - 根据 `session_scope` 和 `conversation_trace` 计算会话 Key
   - 查找或创建对应的 Claude 会话
   - 管理会话生命周期

**示例**：
```bash
# 审计节点为每个前端会话维护一个审计会话
ccm sub auditor worker "!PreToolUse" --session-scope upstream-session

# 日志节点用一个全局会话记录所有事件
ccm sub logger worker "*" --session-scope global

# 协调者在同一个会话中处理来自 B 和 C 的事件
ccm sub coordinator worker "*" --session-scope global:ops-bridge
ccm sub coordinator monitor "*" --session-scope global:ops-bridge
```

### 3.5.2 阻塞事件的等待-唤醒机制

**核心问题**：高层代码不应该关心"到底是 Hook 在等待还是会话在等待"。

**解决方案**：

1. **EventWaiter**（抽象的等待点）：
   ```python
   class EventWaiter:
       async def wait(self, timeout: float) -> Any:
           """阻塞等待，直到被唤醒或超时"""
       
       def resolve(self, result: Any):
           """唤醒等待者"""
   ```

2. **WaiterRegistry**（全局注册表）：
   ```python
   class WaiterRegistry:
       def register(self, event_id: str) -> EventWaiter
       def resolve(self, event_id: str, result: Any)
   ```

3. **MeshOutbox.send_blocking()**（统一接口）：
   ```python
   async def send_blocking(self, event: MeshEvent, timeout: float = 30):
       # 1. 注册 Waiter
       waiter = self.waiter_registry.register(event.event_id)
       # 2. 发送事件
       await self.send(event)
       # 3. 阻塞等待
       result = await waiter.wait(timeout)
       # 4. 返回结果
       return result
   ```

4. **MeshInbox.handle_reply()**（自动触发）：
   ```python
   async def handle_incoming_event(self, event: MeshEvent):
       if isinstance(event, NodeMessage) and event.reply_to:
           waiter = self.waiter_registry.get(event.reply_to)
           if waiter:
               waiter.resolve(event.content)  # 自动唤醒
   ```

**抽象层次**：
```
Hook / Session / 业务逻辑
    ↓ 只调用 send_blocking()
MeshOutbox / MeshInbox
    ↓ 管理 Waiter 注册和触发
WaiterRegistry
    ↓ 解耦等待者和唤醒者
```

### 3.5.3 PreToolUse 阻塞语义澄清

**关键认识**：
1. PreToolUse 是否阻塞取决于**订阅关系**（`!PreToolUse` vs `PreToolUse`），而非事件类型
2. 阻塞订阅的回复必须返回到 **Hook 流程**，才能真正影响工具调用
3. 审计节点可以在自己的**会话中**用 Claude 做决策，但回复通过 **Hook 通道**返回

**完整流程**：
```
1. worker 的 Hook 触发 PreToolUse
   ↓
2. 查询阻塞订阅者 → 发现 auditor
   ↓
3. send_blocking(event) → 注册 Waiter → 阻塞等待
   ↓
4. auditor 的 EventProcessor 收到事件
   ↓
5. SessionManager 根据 session_scope 解析会话
   ↓
6. 在 auditor 的会话中注入事件消息
   ↓
7. auditor 的 Claude 做决策 → 调用 MCP 工具 respond_to_pre_tool_use
   ↓
8. MCP 工具调用 outbox.reply() → 发送回复
   ↓
9. worker 的 Inbox 收到回复 → 触发 Waiter
   ↓
10. worker 的 send_blocking() 返回 → Hook 继续执行
   ↓
11. Hook 根据回复决定 allow/deny → 返回给 Claude Code
```

### 3.5.4 核心组件关系图

```
┌─────────────────────────────────────────────────────────┐
│                    CCNodeRuntime                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ HookHandler  │  │SessionManager│  │EventProcessor│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         └─────────────────┼─────────────────┘           │
│                           │                             │
│  ┌────────────────────────┴──────────────────────────┐  │
│  │              WaiterRegistry                       │  │
│  └────────────────────┬──────────────────────────────┘  │
│                       │                                 │
│  ┌────────────────────┴──────────────────────────────┐  │
│  │         MeshOutbox          MeshInbox             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 遗留问题和待探讨的架构决策

### 4.1 非阻塞订阅的上下文增强 ⭐⭐

**问题描述**：
- 非阻塞订阅的一个用途是让订阅者提供"额外上下文"
- 但如果是非阻塞，TARGET 已经继续执行了
- 如何让 TARGET 收到这些上下文？

**可能方案**：

#### **方案 A: 短暂等待窗口**
```python
# 发送事件后，给非阻塞订阅者一个短暂窗口（如 5 秒）收集上下文
context_messages = await wait_for_context(
    timeout=5.0,
    event_id=event.event_id
)

# 汇总上下文，附加到 Hook 结果
if context_messages:
    additional_context = aggregate_context(context_messages)
    return HookResult(systemMessage=additional_context)
```

#### **方案 B: 三种订阅模式**
```bash
ccm sub auditor worker "!PreToolUse"    # 阻塞（必须等待）
ccm sub context worker "+PreToolUse"    # 上下文模式（短暂等待）
ccm sub logger worker "*"               # 通知模式（完全异步）
```

**需要决定**：
- 是否需要上下文增强功能？
- 如果需要，采用哪种方案？
- 等待窗口多长合适？

---

### 4.2 前端 CC 限制 ⭐⭐

**当前理解**：
- "整个系统最多一个前端 CC"

**问题**：
```bash
# 场景 A: 同一节点
ccm run worker  # Terminal 1
ccm run worker  # Terminal 2  → 应该拒绝 ✅

# 场景 B: 不同节点
ccm run worker     # Terminal 1
ccm run supervisor # Terminal 2  → 允许吗？❓
```

**需要决定**：
- 是否放宽限制，允许多个前端 CC 并行工作？
- 限制的理由是什么？
  - 技术限制？
  - 简化设计？
  - 避免冲突？

**建议**：
- 允许多个前端 CC（不同节点）
- 但同一节点同时只能一个实例
- 同一工作区不能有多个前台 CC（Claude Code 限制）

---

### 4.3 订阅关系：DAG vs 有环图 ⭐⭐⭐

**关键问题**：订阅关系是否允许形成环？

#### **有向无环图（DAG）**
```
     A
    ↙ ↘
   B   C
    ↘ ↙
     D
```
- ✓ 不会无限循环
- ✓ 易于推理
- ✗ 限制表达能力

#### **有环图**
```
   A → B
   ↑   ↓
   ← C ←
```
- ✓ 更灵活（如"循环讨论"）
- ✗ 可能无限循环
- ✗ 需要终止条件

**需要决定**：
1. 是否允许环？
2. 如果允许，如何避免无限循环？
   - 事件 TTL（跳数限制）？
   - 访问历史追踪？
   - 终止条件检测？
3. 是否有必须支持环的场景？

**当前代码**：
- `get_subscription_chain` 会在遇到环时无限递归
- 需要修复（添加 visited 集合）

---

### 4.4 后台 CC 启动时机和生命周期 ⭐⭐

**当前设计**：
- 前端 CC 启动时，所有订阅者立即启动
- 所有后台 CC 的会话生命周期与前端 CC 相同

**问题**：
- 有时希望后台 CC "处理完一个事件就退出"
- 下个事件来临时再启动（按需处理）

**涉及的权衡**：

| 模式 | 会话生命周期 | 优点 | 缺点 |
|------|------------|------|------|
| **Persistent** | 长期运行 | 保留上下文<br>持续监听 | 资源占用<br>会话过长 |
| **Ephemeral** | 一事件一会话 | 资源节省<br>清晰隔离 | 无跨事件上下文<br>启动开销 |
| **Pooled** | 进程池 | 并行处理<br>资源复用 | 实现复杂 |

**需要决定**：
1. 默认采用哪种模式？
2. 是否支持用户选择？
3. 是否需要 CCM Daemon 管理进程生命周期？

---

### 4.5 节点崩溃处理和监控架构 ✅ 已解决

**解决方案**：已在 `crash-recovery.md` 中完整设计

**核心决策**：
1. **Daemon 架构**：
   - 每个 Mesh 一个 Daemon 进程
   - systemd 管理 Daemon（生产环境）
   - 开发环境自动恢复机制

2. **监控机制**：
   - 主要：PID 检测（os.kill(pid, 0)）
   - 辅助：可选心跳机制（检测僵尸进程）
   - 每秒检查一次

3. **重启策略**：
   - 重启模式：always / on-failure / no
   - 指数退避：base * (2 ** crash_count)，最多 5 分钟
   - 最大重试次数：默认 3 次

4. **事件投递保证**：
   - **At-least-once** 语义
   - 恢复窗口机制：processing 状态超过 5 分钟自动重新可见
   - ACK/NACK 机制
   - 业务逻辑需保证幂等性

5. **会话恢复**：
   - Backend Session：按需重建（upstream-session），或启动时重建（global）
   - Interactive Agent：自动重连机制

---

### 4.6 订阅链的语义和用途 ⭐

**当前代码**：
```python
async def get_subscription_chain(target_id: str) -> List[Subscription]:
    """获取订阅链"""
    subscriptions = await get_subscriptions(target_id)  # 谁订阅了 target
    chain = []
    for sub in subscriptions:
        chain.extend(await get_subscription_chain(sub.source_id))  # 递归
    return chain
```

**问题**：
1. 订阅链的方向：
   - "谁订阅了我"（upstream）？
   - "我订阅了谁"（downstream）？

2. 用途：
   - 找到需要启动的后台节点？
   - 如果是，应该是"谁订阅了我"

**示例**：
```bash
ccm sub B A "*"  # B 订阅 A
ccm sub C B "*"  # C 订阅 B

ccm run A
```

**应该启动哪些后台节点？**
- 选项 1: 只启动 B（直接订阅者）
- 选项 2: 启动 B 和 C（订阅链）

**需要明确**：
- 订阅链的精确定义
- 递归查询的边界条件
- 是否需要订阅链，还是只需要"直接订阅者"？

---

### 4.7 事件生命周期和清理策略 ⭐

**当前状态**：
- 事件写入 event_queue 表
- 未实现状态转换
- 未实现清理机制

**需要设计**：

#### **事件状态机**
```
pending → processing → completed
                    → failed → retry_pending
                            → archived
```

#### **清理策略**
- 何时删除已完成的事件？
  - 立即删除？
  - 保留 N 天？
  - 归档到另一个表？
- 失败事件如何处理？
  - 重试？
  - 告警？
  - 人工介入？

**需要决定**：
1. 事件状态模型
2. 清理策略（TTL, 手动清理, 自动归档）
3. 审计需求（是否需要长期保留事件历史）

---

### 4.8 Hook 在后台 CC 中的触发 ⚠️

**我的理解可能有误**，需要进一步澄清：

**我之前认为**：Hook 只在前端 CC 触发

**实际应该是**：Hook 在任何 CC 实例（前台或后台）中都会触发

**问题**：
1. 后台 CC 的 Hook 事件是否也应该传播到 Mesh？
   - 如果是，可能形成事件级联
   - 如何避免事件风暴？

2. 示例场景：
   ```
   前端 CC (worker) 触发 PreToolUse
     → 发送给后台 CC (supervisor)
     → supervisor 处理时也使用了工具
     → supervisor 的 PreToolUse Hook 触发
     → 是否也发送给它的订阅者？
     → 可能形成无限链
   ```

3. 如何区分：
   - 前端 CC 的事件（应该传播）
   - 后台 CC 的事件（可能不应该传播？）

**需要澄清**：
- Hook 在后台 CC 中如何触发？
- 后台 CC 的 Hook 事件如何处理？
- 是否需要"事件来源标识"（origin_id vs source_id）？

---

### 4.9 NodeMessage 的完整用途和扩展性 ⭐

**当前理解**：
- NodeMessage 用于响应 Hook 事件（通过 reply_to 字段）
- 节点也可以主动发送 NodeMessage（通过 MCP 工具）

**问题**：
1. 主动发送 NodeMessage 的用途？
   - 节点间通信？
   - 协作协调？

2. 如何发送？
   - 需要提供 MCP 工具吗？
   ```python
   @mcp.tool()
   async def send_message_to_node(
       target_node_id: str,
       content: Dict
   ):
       ...
   ```

3. 未来如何支持自定义事件类型？
   - 用户定义新的事件类？
   - 动态注册事件类型？
   - 插件机制？

**需要明确**：
- NodeMessage 的完整使用场景
- 事件扩展的机制
- 是否需要事件注册表？

---

### 4.10 系统边界和多租户 ⭐

**问题**：
1. 一个 Mesh 系统的边界是什么？
   - 共享同一个数据库？
   - 明确定义的节点集合？

2. 多个独立 Mesh 系统可以共存吗？
   ```bash
   # 项目 A 的 Mesh
   ccm --workspace ~/project-a init
   ccm create worker-a
   
   # 项目 B 的 Mesh
   ccm --workspace ~/project-b init
   ccm create worker-b
   ```

3. 节点发现：
   - 节点如何知道其他节点的存在？
   - 只通过订阅关系？
   - 需要节点注册表吗？

**需要决定**：
- 是否支持多 Mesh 系统？
- 隔离机制（不同数据库？命名空间？）
- 节点发现和注册机制
- 文件命名规范：当前建议使用 `~/.mosaic/<mesh_id>/mesh.db` 与 `~/.mosaic/<mesh_id>/sockets/<node_id>.sock`，是否需要可配置？

---

### 4.11 Mosaic 抽象层的落地方式 ⭐⭐

**规范现状**：`event-system-spec.md` 已定义 MeshClient / MeshInbox / MeshOutbox / MeshAdmin / MeshContext，但代码层尚未实现。

**需要明确**：
1. 抽象与当前实现的映射方式：现有 `Inbox`/`Outbox` 类是否直接升级，还是新建接口层？
2. `EventEnvelope` 的 ACK 语义与 SQLite schema 的对应字段（pending/processing/completed）如何实现？
3. `MeshContext` 数据来源：拓扑与语义信息由何处生成？如何在节点启动时注入 Prompt？

---

### 4.12 Claude CLI 的 PTY Wrapper ⭐⭐

**背景**：当 CC 节点以 `claude` CLI 形式运行且同时接受用户输入时，Mesh 事件也需要注入同一 CLI 会话，必须避免输入输出互相干扰。

**设计要点**：
- 通过 `pty`/`pexpect` 创建“边车”进程，托管 `stdin/stdout`。
- 维护 CLI 状态机（Idle / Busy / User typing）；仅在安全时注入 Mesh 事件，否则缓冲并提示。
- 解析 CLI 输出，将 Claude 发起的 MCP 调用转回 `MeshOutbox`。

**待办**：
1. 明确 Wrapper 属于 `nodes/claude/cli_runner.py`，底层 PTY 操作封装在 `utils/terminal.py`。
2. 设计事件注入协议（系统消息格式、与用户输入的区分）。
3. 定义 CLI 节点如何声明其事件能力（与 `register_node_capabilities` 对齐）。

---

## 5. 我尚未理解清楚的地方

### 5.1 Program 模式的技术实现细节 ⚠️

**已理解**：
- ✅ Program 模式是"离线培训"
- ✅ 用户通过对话配置节点职责
- ✅ 持久化方式由用户决定（CLAUDE.md 或 MCP memory）

**未理解**：
- ❓ `run_program()` 方法应该具体做什么？
  ```python
  async def run_program(self):
      # 1. 启动 CC 交互界面？如何启动？
      # 2. 注入什么样的系统提示词？
      # 3. 如何"断开 Mesh 连接"？
      # 4. 如何让 CC "知道但不能用" MCP 工具？
      # 5. 结束条件是什么？
      pass
  ```

- ❓ 系统提示词的具体内容？
  ```python
  system_prompt = f"""
  你是 Mesh 网络中的 {node_id} 节点。
  你的订阅关系：{subscriptions}
  
  注意：当前处于 Program 模式，Mesh 功能已禁用。
  你可以看到但不能使用以下 MCP 工具：
  - respond_to_pre_tool_use
  - ...
  
  请与用户讨论你的职责和工作方式...
  """
  ```

- ❓ 如何从 Program 模式"加载配置"到 Run 模式？
  - 读取 CLAUDE.md 的内容？
  - 查询 MCP memory？
  - 加载到系统提示词？

---

### 5.2 后台 CC 会话的实际代码流程 ⚠️

**已理解**：
- ✅ 使用 claude-agent-sdk
- ✅ 创建持续会话
- ✅ 事件投递到会话

**未理解**：
- ❓ claude-agent-sdk 的具体 API？
  ```python
  from claude_agent_sdk import Agent
  
  agent = Agent(...)  # 参数是什么？
  session = agent.create_session()  # 这个 API 存在吗？
  session.set_system_prompt(...)  # 这个 API 存在吗？
  await session.send_message(...)  # 异步还是同步？
  ```

- ❓ MCP 工具如何集成到 agent？
  - 自动加载 .mcp.json？
  - 手动注册？

- ❓ 会话如何"知道"调用 MCP 工具？
  - 依赖 Claude 的理解能力？
  - 还是有明确的工作流程？

---

### 5.3 非阻塞订阅的上下文增强的实际价值 ⚠️

**已理解**：
- ✅ 你提到"比较纠结"
- ✅ 主要用途是提供额外上下文

**未理解**：
- ❓ 实际使用场景是什么？
  - 能举个具体例子吗？
  - 什么样的上下文？
  - 如何影响决策？

- ❓ 是否真的需要这个功能？
  - 还是可以用阻塞订阅 + 窗口期替代？
  - 还是完全不需要（只用于日志）？

---

### 5.4 Hook 在后台 CC 中的触发机制 ⚠️⚠️

**已知我的理解有误**，但仍不清楚：

- ❓ 后台 CC 也会触发 Hook 吗？
  - 如果后台 CC 使用了工具，PreToolUse Hook 触发吗？
  - 如果触发，事件发送给谁？

- ❓ 如何配置后台 CC 的 Hook？
  - 也是通过 .claude/settings.json？
  - 还是不同的配置？

- ❓ 能否举个完整的事件流示例？
  ```
  前端 worker 触发事件 A
    → 后台 supervisor 处理事件 A
    → supervisor 使用工具 B
    → supervisor 的 Hook 触发？
    → 事件 B 发送给谁？
    → ...
  ```

---

### 5.5 多个阻塞订阅者的并发处理 ⚠️

**已理解**：
- ✅ 一票否决制
- ✅ 汇总理由

**未理解**：
- ❓ 如何"同时"发送给多个订阅者？
  - `batch_send_and_wait` 并发发送？
  - 还是串行发送？

- ❓ 如果订阅者响应速度不一？
  - 等待所有人？
  - 还是有超时？

- ❓ 代码实现示例？
  ```python
  blocking_subscribers = [A, B, C]
  
  # 并发发送
  events = [create_event(sub) for sub in blocking_subscribers]
  responses = await batch_send_and_wait(events, timeout=30)
  
  # 聚合决策
  final_decision = aggregate(responses)  # 如何聚合？
  ```

---

### 5.6 工作区 (workspace) 的确切作用 ⚠️

**已理解**：
- ✅ workspace 是 Claude Code 的概念，非 CCM 引入

**未理解**：
- ❓ workspace 在 CCM 中的作用？
  - 只是 CC 的工作目录？
  - 还是配置文件的存放位置？

- ❓ 多个节点能共享 workspace 吗？
  - 如果不能，是 CCM 的限制还是 CC 的限制？

- ❓ workspace 与节点的映射关系？
  - 1:1 强制绑定？
  - 还是可以多对一？

---

### 5.7 前端 CC 限制的确切原因 ⚠️

**已理解**：
- ✅ "最多一个前端 CC"

**未理解**：
- ❓ 这个限制的确切原因是什么？
  - 技术限制（如数据库锁）？
  - 设计简化？
  - 避免某种冲突？

- ❓ 如果放宽限制，会有什么问题？
  - 多个前端 CC 同时运行
  - 是否会导致竞态条件？
  - 还是完全可行，只是当前没实现？

---

### 5.8 订阅链在 run_interactive 中的确切用途 ⚠️

**已理解**：
- ✅ run_interactive 时查询订阅链
- ✅ 启动订阅链中的后台节点

**未理解**：
- ❓ 订阅链的精确定义？
  - 从 worker 向上查找所有订阅者？
  - 还是包括订阅者的订阅者（递归）？

- ❓ 示例场景的正确行为？
  ```bash
  ccm sub B A "*"
  ccm sub C B "*"
  
  ccm run A
  
  # 应该启动：
  # 选项 1: 只启动 B（直接订阅者）
  # 选项 2: 启动 B 和 C（递归订阅链）
  # 选项 3: 其他？
  ```

- ❓ 当前代码的问题？
  - 递归方向错了？
  - 还是逻辑正确但有 bug？

---

## 6. 下一步行动建议

### 6.1 立即可做（概念已清晰）

1. **✅ 更新文档**
   - 更新 `concepts-and-features.md` 反映本次讨论的澄清
   - 更新 `architecture.md` 增加后台 CC 工作机制的详细说明

2. **✅ 修复严重 Bug**（4 个 Critical Issues）
   - 实现 `Node.from_dict()` 等方法
   - 修复 `ClaudeCode.__init__`
   - 修复 `HookRunner.handlers`
   - 实现 `ClaudeCode.run()`

### 6.2 需要进一步讨论（架构决策）

在实施前，需要明确以下设计决策：

**优先级 1 (Critical)**：
1. **订阅链的精确语义** - 影响 run_interactive 的实现
2. **后台 CC 的会话模式** - Persistent vs Ephemeral
3. **Hook 在后台 CC 中的触发** - 避免事件风暴

**优先级 2 (High)**：
4. **节点崩溃处理** - 是否需要 CCM Daemon
5. **订阅关系是否允许环** - 影响数据验证
6. **事件生命周期管理** - 状态机和清理策略

**优先级 3 (Medium)**：
7. **非阻塞订阅的上下文模式** - 是否需要实现
8. **前端 CC 限制** - 是否放宽
9. **系统边界和多租户** - 是否支持

### 6.3 需要技术细节澄清

1. **claude-agent-sdk 的 API 用法**
2. **Program 模式的具体实现步骤**
3. **后台 CC 会话的代码示例**
4. **工作区的确切作用和限制**

---

## 7. 总结

### 7.1 所有会话的成果总结 ✅

#### 2025-11-23 会话成果

1. **✅ 核心概念已对齐**
   - 节点、事件、订阅、Program 模式
   - 一节点一进程架构
   - 后台 CC 工作机制

2. **✅ 事件系统抽象层确定**
   - MeshClient / MeshInbox / MeshOutbox
   - MeshAdmin / MeshContext
   - 多 Mesh 隔离机制

3. **✅ 识别了所有严重问题**
   - 4 个 Critical Bugs
   - 部分实现和未实现的功能

#### 2025-11-24 会话成果

1. **✅ 会话对齐机制设计完成**
   - ConversationTrace：事件中的会话溯源
   - Session Scope：订阅关系中的会话作用域
   - SessionManager：会话解析与管理

2. **✅ 阻塞事件的等待-唤醒机制设计完成**
   - EventWaiter + WaiterRegistry：通用的阻塞抽象
   - 高层代码统一接口：`send_blocking()`
   - 支持多订阅者并发等待和决策聚合

3. **✅ CC 节点事件处理流程设计完成**
   - EventProcessor：事件分发
   - HookHandler：Hook 事件处理（基于新的阻塞机制）
   - MCP 工具：回复阻塞事件

4. **✅ PreToolUse 阻塞语义澄清**
   - 阻塞与否由订阅关系决定，而非事件类型
   - 回复必须返回到 Hook 流程才能影响工具调用
   - 审计节点在会话中决策，但通过 Hook 通道回复

#### 完整文档体系

- `concepts-and-features.md`: 概念和功能详解
- `architecture.md`: 系统架构设计
- `refactoring-plan.md`: 重构计划
- `README.md`: 项目介绍
- `docs/architecture/event-system-spec.md`（v1.4）: Mosaic 抽象层规范
- `docs/architecture/cc-node-event-integration.md`（2025-11-24）: CC 节点与事件系统集成设计
- `docs/project-understanding-and-tasks.md`（本文档）: 项目理解与工作记录

### 7.2 下次会话的重点 🎯

**建议下次会话的目标**：

1. **实现 CC 节点集成的核心组件**：
   - WaiterRegistry + EventWaiter
   - SessionManager
   - EventProcessor
   - HookHandler（基于新的阻塞机制）

2. **明确剩余的架构决策**（第 4 节中的问题）：
   - 后台 CC 的启动时机和生命周期策略
   - 节点崩溃处理和监控架构
   - 订阅关系是否允许环

3. **澄清技术实现细节**（第 5 节中的疑问）：
   - claude-agent-sdk 的具体 API
   - Program 模式的实现细节
   - 工作区的确切作用

4. **开始原型实现**：
   - 基于 `cc-node-event-integration.md` 实现一个最小可用原型
   - 验证会话对齐和阻塞机制的可行性

### 7.3 关键提醒 ⚠️

**在下次实施前，务必明确**：
- ✅ 订阅链的精确定义和用途
- ✅ 后台 CC 的 Hook 触发机制
- ✅ 节点崩溃处理方案
- ✅ 事件生命周期管理

**避免过早实施**：
- ⚠️ 在架构决策未明确前，不要大规模重构
- ⚠️ 优先修复 Critical Bugs，确保基本功能可运行
- ⚠️ 通过原型验证不确定的设计

---

## 8. 快速索引

### 8.1 核心概念速查

- **节点与会话关系**：见 § 1.2 概念 1
- **事件类型**：见 § 1.2 概念 2
- **订阅关系（阻塞/非阻塞）**：见 § 1.2 概念 3
- **Program 模式**：见 § 1.2 概念 4
- **后台 CC 工作机制**：见 § 1.2 概念 6

### 8.2 本次会话（2025-11-24）核心设计

- **会话对齐机制**：见 § 3.5.1
- **阻塞事件的等待-唤醒机制**：见 § 3.5.2
- **PreToolUse 阻塞语义**：见 § 3.5.3
- **核心组件关系图**：见 § 3.5.4
- **完整设计文档**：`docs/architecture/cc-node-event-integration.md`

### 8.3 待解决问题

- **架构决策**：见 § 4（4.1-4.12）
- **技术细节疑问**：见 § 5（5.1-5.8）
- **下一步行动**：见 § 6

### 8.4 关键设计原则

1. **会话对齐由订阅关系声明**，而非事件发送方
2. **阻塞等待抽象化**，高层代码不关心具体机制
3. **事件携带溯源信息**，提供上下文来源
4. **一节点一进程**，节点内部会话策略灵活

---

---

## 9. 本次会话（第二阶段）核心成果总结

### 9.1 解决的关键问题

1. **✅ 崩溃恢复的完整方案**：
   - Daemon + systemd 保证系统级可靠性
   - At-least-once 事件投递保证
   - 恢复窗口机制（5 分钟）
   - 节点重启策略（always/on-failure）

2. **✅ 多会话并发处理**：
   - 派发型策略（random, round-robin, load-balanced, sticky-source）
   - Session Filter（backend-only, interactive-first）
   - Backend Session 轻量级实现（claude-agent-sdk）

3. **✅ 进程架构澄清**：
   - Agent Process 与 Node Runtime 是协作关系（IPC），非父子关系
   - Backend Session：非独立进程，在 Runtime 内部
   - Interactive Agent：独立进程，用户可交互

4. **✅ 术语体系统一**：
   - 全部使用 Session 术语
   - SessionTrace, BackendSession, SessionManager
   - 清晰的会话标识体系

5. **✅ 数据库架构简化**：
   - 统一数据库 `~/.mosaic/mosaic.db`
   - mesh_id 字段区分
   - 简化部署和备份

### 9.2 完整的文档体系

| 文档 | 内容 | 状态 |
|------|------|------|
| `concepts-glossary.md` | 核心概念词汇表，术语统一 | ✅ 新增 |
| `crash-recovery.md` | 崩溃恢复完整设计 | ✅ 新增 |
| `cc-node-event-integration.md` | CC 节点集成设计（已更新 Session Scope 扩展） | ✅ 更新 |
| `event-system-spec.md` | 事件系统抽象层（v1.4） | ⏸️ 需要更新 |
| `project-understanding-and-tasks.md` | 项目理解与任务（本文档） | ✅ 更新 |

### 9.3 架构关键设计点

```
Daemon Process (systemd 管理)
    ↓ 监控
Node Runtime Process (常驻，事件系统进程)
    ├─ Backend Session (claude-agent-sdk，轻量级)
    │   ├─ per-event：一事件一会话
    │   ├─ upstream-session：跟随上游
    │   ├─ global：全局共享
    │   └─ round-robin：会话池（派发型）
    │
    └─ Interactive Agent Proxy (代理)
        ↕ IPC
    Interactive Agent Process (独立 Claude Code)
```

### 9.4 下次会话建议

**可以开始的工作**：
1. **原型实现**：基于三个文档实现最小可用原型
2. **API 确认**：确认 claude-agent-sdk 的具体 API
3. **测试场景**：设计并实现关键测试场景
4. **剩余决策**：明确非阻塞上下文增强、订阅环等

**优先级排序**：
1. 实现 WaiterRegistry + EventWaiter（阻塞机制）
2. 实现 SessionResolver（会话路由）
3. 实现 Backend Session（使用 claude-agent-sdk）
4. 实现崩溃恢复的基础框架

---

**文档结束**

_下次会话请先阅读 § 0（最新结论速览），快速恢复上下文。三个新文档（concepts-glossary.md, crash-recovery.md, cc-node-event-integration.md）包含完整的设计细节。_

