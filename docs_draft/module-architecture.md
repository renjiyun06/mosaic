# Mosaic 模块架构设计

> **文档用途**: 定义 Mosaic 项目的模块划分、职责边界和依赖关系  
> **创建日期**: 2025-11-24  
> **目标读者**: 开发者、架构师

---

## 1. 概述

### 1.1 架构原则

Mosaic 项目采用**分层架构**和**插件化设计**，遵循以下核心原则：

1. **抽象分离**: 核心抽象层（`core`）与具体实现完全解耦
2. **传输可插拔**: 支持多种传输后端（SQLite、Kafka、Redis）
3. **节点类型插件化**: 不同类型的节点作为独立插件实现
4. **单向依赖**: 严格控制模块间依赖方向，避免循环依赖
5. **智能体特化**: Session 等概念仅存在于智能体节点，不是事件系统的一部分

### 1.2 顶层目录结构

```
mosaic/
├── src/mosaic/             # 主包
│   ├── core/               # 核心抽象层
│   ├── transport/          # 传输层（可插拔）
│   ├── storage/            # 持久化层
│   ├── runtime/            # 运行时基础设施
│   ├── nodes/              # 节点类型实现（插件化）
│   ├── daemon/             # Daemon 进程
│   ├── cli/                # 命令行工具
│   └── utils/              # 工具库
├── tests/
├── docs/
└── examples/
```

---

## 2. 核心模块详解

### 2.1 `mosaic.core` - 核心抽象层

**职责**: 定义整个 Mosaic 事件系统的契约和接口规范

**设计原则**:
- 只包含抽象基类（ABC）和数据模型
- 不包含任何具体实现逻辑
- 所有其他模块的基础依赖
- 对应 `docs/architecture/event-system-spec.md`

#### 2.1.1 目录结构

```
core/
├── __init__.py
├── interfaces.py            # 核心接口定义（ABC）
├── models.py                # 数据模型
├── types.py                 # 类型定义和枚举
└── exceptions.py            # 异常类定义
```

#### 2.1.2 提供的接口

##### **interfaces.py - 事件系统接口**

定义所有核心接口（抽象基类），作为系统的契约层。

**命名说明**:
- 使用 `interfaces.py` 而非 `abstractions.py`
- 更清晰地表达"接口定义"的含义
- 符合常见的命名约定（如 Java 的 interfaces, Go 的 interfaces）

```python
# 数据平面（Data Plane）
class MeshClient(ABC):
    """节点接入 Mesh 网络的运行时接口"""
    - node_id: str
    - mesh_id: str
    - inbox: MeshInbox
    - outbox: MeshOutbox
    - context: MeshContext

class MeshInbox(ABC):
    """事件输入通道（异步迭代器模式）"""
    - __aiter__() -> AsyncIterator[EventEnvelope]

class MeshOutbox(ABC):
    """事件输出通道"""
    - send(event: MeshEvent) -> None
    - send_blocking(event: MeshEvent, timeout: float) -> List[Any]
    - reply(event_id: str, payload: Any) -> None

class EventEnvelope(ABC):
    """事件信封（携带 ACK/NACK 方法）"""
    - event: MeshEvent
    - ack() -> None
    - nack(requeue: bool) -> None

# 控制平面（Control Plane）
class MeshAdmin(ABC):
    """网络配置和管理接口"""
    - create_node(node_id: str, config: dict) -> None
    - subscribe(subscription: Subscription) -> None
    - register_node_capabilities(capabilities: dict) -> None

# 上下文平面（Context Plane）
class MeshContext(ABC):
    """拓扑和语义信息查询接口"""
    - get_topology_context() -> TopologyContext
    - get_event_semantics(event_types: List[str]) -> Dict[str, EventSemantics]
```

##### **models.py - 数据模型**

```python
核心数据模型（使用 Pydantic）:

- MeshEvent: 事件基类
  - event_id: str
  - source_id: str
  - target_id: str
  - timestamp: datetime
  - session_trace: Optional[SessionTrace]

- SessionTrace: 会话溯源信息（元数据）
  - node_id: str
  - upstream_session_id: str
  - event_seq: int
  
  注意：对事件系统来说，这只是一个普通的元数据字段
       具体如何使用由接收方节点决定（智能体节点会用到）

- Subscription: 订阅关系
  - source_id: str (订阅者/下游)
  - target_id: str (被订阅者/上游)
  - event_pattern: str (支持 !EventName 表示阻塞)
  - session_scope: Optional[str] (对智能体节点有意义的配置)
  - session_filter: Optional[str]
  - session_profile: Optional[str]

- Node: 节点定义
  - node_id: str
  - mesh_id: str
  - node_type: str
  - workspace: Optional[str]
  - config: dict

- TopologyContext: 拓扑上下文
  - subscriptions: List[Subscription] (我订阅了谁)
  - subscribers: List[Subscription] (谁订阅了我)
```

##### **types.py - 类型定义**

```python
枚举和类型别名:

- NodeType: 节点类型（"cc", "scheduler", "webhook"）
- EventType: 事件类型（"PreToolUse", "PostToolUse", etc.）
- SessionScope: 会话作用域策略（仅对智能体节点有意义）
- RestartPolicy: 重启策略配置
```

#### 2.1.3 关键设计点

1. **Session 不是事件系统概念**: 
   - `SessionTrace` 只是事件的元数据字段
   - `session_scope` 等是订阅关系的"不透明配置"
   - 事件系统不解释这些字段，只是透传
   - 具体如何使用由接收方节点决定（智能体节点会用到，非智能体节点忽略）

2. **抽象稳定性**: 
   - `core` 模块定义的接口应保持高度稳定
   - 任何修改都需要慎重考虑向后兼容性

3. **依赖关系**:
   - `core` 不依赖任何其他模块
   - 所有模块都可以依赖 `core`

---

### 2.2 `mosaic.transport` - 传输层

**职责**: 提供可插拔的事件传输后端实现

**设计原则**:
- 定义传输层抽象接口
- 支持多种传输后端（SQLite、Kafka、Redis）
- 与业务逻辑解耦

#### 2.2.1 目录结构

```
transport/
├── __init__.py
├── base.py                  # 传输层抽象
├── sqlite/                  # SQLite + UDS 实现
│   ├── __init__.py
│   ├── backend.py           # SQLiteTransportBackend
│   ├── database.py          # 事件数据库管理（内部）
│   ├── repository.py        # EventRepository（内部）
│   ├── inbox.py             # SQLite 的 Inbox 实现
│   ├── outbox.py            # SQLite 的 Outbox 实现
│   └── signal.py            # UDS 信号机制
│       ├── SignalListener
│       └── SignalClient
├── kafka/                   # 未来: Kafka 实现
│   ├── __init__.py
│   ├── backend.py           # KafkaTransportBackend
│   ├── producer.py          # Kafka Producer（内部）
│   └── consumer.py          # Kafka Consumer（内部）
└── redis/                   # 未来: Redis 实现
    ├── __init__.py
    ├── backend.py           # RedisTransportBackend
    └── stream.py            # Redis Stream（内部）
```

**关键点**:
- 每种传输实现都有自己的内部数据存储机制
- SQLite 实现：使用 `database.py` 和 `repository.py` 管理事件数据库
- Kafka 实现：使用 Kafka Topic 存储事件
- Redis 实现：使用 Redis Stream 存储事件
- 这些都是传输层的实现细节，不暴露给外部

#### 2.2.2 提供的抽象

##### **base.py - 传输层接口**

```python
class TransportBackend(ABC):
    """传输层抽象接口"""
    
    @abstractmethod
    async def send_event(self, event: MeshEvent) -> None:
        """发送事件到传输层"""
        pass
    
    @abstractmethod
    async def receive_events(self, node_id: str) -> AsyncIterator[EventEnvelope]:
        """接收事件的异步迭代器"""
        pass
    
    @abstractmethod
    async def ack_event(self, event_id: str) -> None:
        """确认事件处理完成"""
        pass
    
    @abstractmethod
    async def nack_event(self, event_id: str, requeue: bool) -> None:
        """拒绝事件（可选重新入队）"""
        pass

职责:
- 事件的持久化存储
- 事件的可靠传输
- At-least-once 投递语义
- 进程间通知机制
```

##### **sqlite/backend.py - SQLite 实现**

```python
class SQLiteTransportBackend(TransportBackend):
    """基于 SQLite + UDS 的传输实现"""
    
    特点:
    - 使用 SQLite 持久化事件（WAL 模式）
    - 通过 UDS (Unix Domain Socket) 进行进程间信号通知
    - 支持多 Mesh 隔离（通过 mesh_id 字段）
    - 恢复窗口机制（processing 状态超时自动重新可见）
    
    内部组件:
    - EventDatabase: 事件数据库管理（内部实现）
    - EventRepository: 事件的 CRUD 操作（内部实现）
    - UDSSignalTransport: UDS 信号机制
    
    实现:
    async def send_event(event):
        1. 写入数据库（event_queue 表）
        2. 通过 UDS 发送唤醒信号给接收方
    
    async def receive_events(node_id):
        while True:
            1. 查询数据库（status = 'pending' 或超时的 'processing'）
            2. 如果有事件，返回 EventEnvelope
            3. 如果没有，等待 UDS 信号
    
    数据库 Schema (内部):
    CREATE TABLE event_queue (
        id INTEGER PRIMARY KEY,
        mesh_id TEXT NOT NULL,
        event_id TEXT NOT NULL UNIQUE,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        type TEXT NOT NULL,
        payload TEXT NOT NULL,  -- JSON 序列化的完整事件
        status TEXT DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    注意:
    - 这是数据平面的数据库（~/.mosaic/<mesh_id>/events.db）
    - 与控制平面的数据库（~/.mosaic/control.db）分离
    - EventRepository 是 SQLiteTransportBackend 的内部实现，不暴露给外部
```

##### **sqlite/signal.py - UDS 信号机制**

```python
职责:
- 进程间的轻量级通知机制
- 避免轮询数据库

class SignalListener:
    """监听 UDS 信号"""
    - socket_path: Path (~/.mosaic/<mesh_id>/sockets/<node_id>.sock)
    - wait_for_signal() -> None
    
class SignalClient:
    """发送 UDS 信号"""
    - notify(node_id: str) -> None
    - 发送单字节唤醒信号
```

#### 2.2.3 关键设计点

1. **可插拔性**:
   - 通过依赖注入切换传输后端
   - 业务逻辑不依赖具体的传输实现

2. **SQLite 实现特点**:
   - 适合单机部署和开发环境
   - WAL 模式支持并发读写
   - UDS 提供低延迟通知

3. **未来扩展**:
   - Kafka: 分布式部署，高吞吐
   - Redis: 低延迟，支持 Pub/Sub

---

### 2.3 `mosaic.storage` - 控制平面持久化

**职责**: 存储和管理控制平面的元数据（节点、订阅、Mesh 配置）

**设计原则**:
- 只负责控制平面的数据，不负责事件存储
- 事件存储是传输层的实现细节，在 `transport` 模块内部
- 封装数据库操作细节
- 提供高层业务友好的查询接口
- 支持多 Mesh 隔离

#### 2.3.1 目录结构

```
storage/
├── __init__.py
├── database.py              # 数据库连接管理
├── schema.py                # 控制平面 Schema 定义
├── repositories/            # Repository 模式
│   ├── __init__.py
│   ├── base.py              # BaseRepository
│   ├── mesh_repo.py         # MeshRepository
│   ├── node_repo.py         # NodeRepository
│   └── subscription_repo.py # SubscriptionRepository
└── migrations/              # 数据库迁移脚本
    ├── v1_initial.sql
    └── v2_add_xxx.sql
```

**注意**: 不包含 `EventRepository`，事件存储在 `transport` 模块内部实现

#### 2.3.2 提供的抽象

##### **database.py - 数据库管理**

```python
class DatabaseManager:
    """控制平面数据库连接和生命周期管理"""
    
    职责:
    - 管理 SQLite 连接池（控制平面数据库）
    - WAL 模式配置
    - 事务管理
    - 数据库初始化和迁移
    
    方法:
    - get_connection() -> Connection
    - execute(query, params) -> Result
    - execute_many(query, params_list) -> None
    - transaction() -> AsyncContextManager
    
    注意:
    - 这是控制平面的数据库（~/.mosaic/control.db）
    - 事件数据的存储由 transport 模块管理
```

##### **repositories/base.py - Repository 基类**

```python
class BaseRepository(ABC):
    """Repository 模式的基类"""
    
    提供:
    - 通用的 CRUD 操作
    - mesh_id 隔离查询
    - 参数化查询（防止 SQL 注入）
```

##### **repositories/mesh_repo.py - Mesh Repository**

```python
class MeshRepository:
    """Mesh 配置的数据访问层"""
    
    核心方法:
    - create(mesh_id: str, config: dict) -> None
    - get(mesh_id: str) -> Optional[Mesh]
    - list_all() -> List[Mesh]
    - delete(mesh_id: str) -> None
```

##### **repositories/node_repo.py - Node Repository**

```python
class NodeRepository:
    """节点定义的数据访问层"""
    
    核心方法:
    - create(node: Node) -> None
    - get(mesh_id: str, node_id: str) -> Optional[Node]
    - list_by_mesh(mesh_id: str) -> List[Node]
    - update(node: Node) -> None
    - delete(mesh_id: str, node_id: str) -> None
    
    特点:
    - 存储节点的元数据（类型、配置、工作区路径）
    - 不存储节点的运行时状态（PID 等）
```

##### **repositories/subscription_repo.py - Subscription Repository**

```python
class SubscriptionRepository:
    """订阅关系的数据访问层"""
    
    核心方法:
    - create(subscription: Subscription) -> None
    - get_by_source(mesh_id: str, source_id: str) -> List[Subscription]
      查询某节点订阅了谁
    
    - get_by_target(mesh_id: str, target_id: str) -> List[Subscription]
      查询谁订阅了某节点
    
    - get_blocking_subscribers(mesh_id: str, target_id: str, event_type: str) -> List[str]
      查询阻塞订阅者（event_pattern 以 ! 开头）
    
    - delete(mesh_id: str, source_id: str, target_id: str, pattern: str) -> None
```

#### 2.3.3 控制平面数据库 Schema

```sql
-- Mesh 实例定义
CREATE TABLE meshes (
    mesh_id TEXT PRIMARY KEY,
    config TEXT,  -- JSON（可选的 Mesh 级别配置）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 节点定义（元数据）
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    mesh_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    workspace TEXT,
    config TEXT,  -- JSON（节点配置）
    restart_policy TEXT DEFAULT 'on-failure',  -- always/on-failure/no
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mesh_id, node_id)
);
CREATE INDEX idx_nodes_mesh ON nodes(mesh_id);

-- 订阅关系
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    mesh_id TEXT NOT NULL,
    source_id TEXT NOT NULL,       -- 订阅者（下游）
    target_id TEXT NOT NULL,       -- 被订阅者（上游）
    event_pattern TEXT NOT NULL,   -- 事件模式（支持 !EventName）
    
    -- Session 相关配置（仅对智能体节点有意义）
    session_scope TEXT DEFAULT 'upstream-session',
    session_filter TEXT DEFAULT 'any',
    session_profile TEXT DEFAULT 'default',
    min_conversations INTEGER DEFAULT 1,
    max_conversations INTEGER DEFAULT 10,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mesh_id, source_id, target_id, event_pattern)
);
CREATE INDEX idx_subscriptions_mesh ON subscriptions(mesh_id);
CREATE INDEX idx_subscriptions_source ON subscriptions(mesh_id, source_id);
CREATE INDEX idx_subscriptions_target ON subscriptions(mesh_id, target_id);

-- 节点能力注册（可选）
CREATE TABLE node_capabilities (
    id INTEGER PRIMARY KEY,
    mesh_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    direction TEXT NOT NULL,  -- 'produce' 或 'consume'
    schema TEXT,              -- JSON Schema
    description TEXT,         -- 自然语言描述
    UNIQUE(mesh_id, node_type, event_type, direction)
);
```

#### 2.3.4 关键设计点

1. **控制平面专注**: 
   - 只存储元数据（节点定义、订阅关系）
   - 不存储事件数据（事件存储在 `transport` 内部）
   - 不存储运行时状态（PID、状态等由 Daemon 管理）

2. **多 Mesh 隔离**: 
   - 所有表包含 `mesh_id` 字段
   - 通过索引优化查询

3. **与传输层分离**: 
   - `storage` 不依赖具体的传输实现
   - 事件如何存储由 `transport` 决定

4. **Repository 模式**: 
   - 封装 SQL 细节
   - 提供业务友好的接口

---

### 2.4 `mosaic.runtime` - 运行时基础设施

**职责**: 提供与传输和节点类型无关的运行时基础设施

**设计原则**:
- 不依赖具体的传输实现（通过依赖注入）
- 不依赖具体的节点类型
- 提供通用的运行时组件（阻塞等待、事件路由）

#### 2.4.1 目录结构

```
runtime/
├── __init__.py
├── client.py                # MeshClient 实现（组装器）
├── admin.py                 # MeshAdmin 实现
├── context.py               # MeshContext 实现
├── waiter.py                # 阻塞等待机制
└── event_router.py          # 事件路由器
```

#### 2.4.2 提供的组件

##### **client.py - MeshClient 实现**

```python
class MeshClientImpl(MeshClient):
    """MeshClient 的默认实现（组装器）"""
    
    职责:
    - 组合传输层和运行时组件
    - 实现 MeshClient 接口
    
    组成:
    - transport: TransportBackend (依赖注入)
    - waiter_registry: WaiterRegistry
    - inbox: 适配器（transport + waiter_registry）
    - outbox: 适配器（transport + waiter_registry）
    - context: MeshContext 实现
    
    特点:
    - 传输层可插拔（通过构造函数注入）
    - 将底层传输接口适配为 MeshInbox/MeshOutbox
```

##### **waiter.py - 阻塞等待机制**

```python
class EventWaiter:
    """抽象的等待点（基于 asyncio.Future）"""
    
    职责:
    - 封装阻塞等待逻辑
    - 支持超时
    - 解耦等待者和唤醒者
    
    方法:
    - wait(timeout: float) -> Any
      阻塞等待，直到被唤醒或超时
    
    - resolve(result: Any) -> None
      唤醒等待者
    
    - reject(error: Exception) -> None
      以错误唤醒

class WaiterRegistry:
    """全局等待点注册表"""
    
    职责:
    - 管理 event_id → EventWaiter 的映射
    - 注册和清理 Waiter
    
    方法:
    - register(event_id: str) -> EventWaiter
    - get(event_id: str) -> Optional[EventWaiter]
    - resolve(event_id: str, result: Any) -> None
    - unregister(event_id: str) -> None
    
    使用场景:
    - 阻塞订阅（!EventName）
    - Hook 等待回复
    - 任何需要 Request-Response 模式的场景
```

##### **event_router.py - 事件路由器**

```python
class EventRouter:
    """根据订阅关系路由事件"""
    
    职责:
    - 查询订阅关系
    - 将事件分发给所有订阅者
    - 不关心接收方如何处理事件
    
    方法:
    - route_event(event: MeshEvent) -> None
      1. 查询订阅关系（source 订阅了 target）
      2. 为每个订阅者创建事件副本
      3. 设置 target_id = subscriber_id
      4. 发送事件
    
    - get_blocking_subscribers(event: MeshEvent) -> List[str]
      查询阻塞订阅者（event_pattern 以 ! 开头）
    
    特点:
    - 发送端分发（Sender-side Dispatch）
    - 不解释 session_scope 等字段（只是透传）
```

##### **admin.py - MeshAdmin 实现**

```python
class MeshAdminImpl(MeshAdmin):
    """MeshAdmin 的实现"""
    
    职责:
    - 节点创建和配置
    - 订阅关系管理
    - 能力注册
    
    依赖:
    - NodeRepository
    - SubscriptionRepository
    
    方法:
    - create_node(node_id, config) -> None
    - subscribe(subscription) -> None
    - unsubscribe(source_id, target_id, pattern) -> None
    - register_node_capabilities(capabilities) -> None
```

##### **context.py - MeshContext 实现**

```python
class MeshContextImpl(MeshContext):
    """MeshContext 的实现"""
    
    职责:
    - 提供拓扑信息（我订阅谁/谁订阅我）
    - 提供事件语义信息
    
    方法:
    - get_topology_context() -> TopologyContext
      返回节点的订阅关系（上游和下游）
    
    - get_event_semantics(event_types) -> Dict[str, EventSemantics]
      返回事件类型的语义描述（用于注入 System Prompt）
```

#### 2.4.3 关键设计点

1. **组装器模式**: `MeshClientImpl` 将各个组件组合成完整的客户端
2. **依赖注入**: 传输层通过构造函数注入，实现解耦
3. **通用机制**: WaiterRegistry 是通用的阻塞等待机制，与会话无关
4. **事件路由**: EventRouter 只负责分发，不关心接收方如何处理

---

### 2.5 `mosaic.nodes` - 节点类型实现

**职责**: 不同类型节点的具体实现（插件化架构）

**设计原则**:
- 每种节点类型是独立的子模块
- 实现统一的 `NodeRuntime` 接口
- Session 等概念仅存在于智能体节点，非智能体节点可以完全忽略

#### 2.5.1 目录结构

```
nodes/
├── __init__.py
├── base.py                  # 节点基类和工厂
│   ├── NodeRuntime (ABC)
│   └── NodeFactory
│
├── cc/                      # Claude Code 节点（智能体）
│   ├── __init__.py
│   ├── runtime.py           # CCNodeRuntime
│   ├── event_processor.py   # CC 的事件处理逻辑
│   ├── hook_handler.py      # Hook 事件处理
│   ├── mcp_server.py        # MCP 工具服务器
│   ├── config.py            # CC 节点配置
│   └── session/             # Session 管理（CC 特有）
│       ├── __init__.py
│       ├── manager.py       # CCSessionManager
│       ├── resolver.py      # CCSessionResolver
│       ├── strategies.py    # Session Scope 策略实现
│       ├── backend_session.py   # CCBackendSession
│       └── interactive_proxy.py # InteractiveAgentProxy
│
├── scheduler/               # 调度器节点（非智能体）
│   ├── __init__.py
│   └── runtime.py           # SchedulerNodeRuntime
│
└── webhook/                 # Webhook 节点（非智能体）
    ├── __init__.py
    └── runtime.py           # WebhookNodeRuntime
```

#### 2.5.2 提供的抽象

##### **base.py - 节点基类**

```python
class NodeRuntime(ABC):
    """所有节点类型的统一接口"""
    
    @abstractmethod
    async def start(self) -> None:
        """启动节点运行时"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止节点运行时"""
        pass
    
    @abstractmethod
    async def process_event(self, envelope: EventEnvelope) -> None:
        """处理接收到的事件"""
        pass

class NodeFactory:
    """节点工厂（插件注册）"""
    
    职责:
    - 注册节点类型
    - 根据 node_type 创建对应的 NodeRuntime 实例
    
    用法:
    NodeFactory.register("cc", CCNodeRuntime)
    NodeFactory.register("scheduler", SchedulerNodeRuntime)
    
    runtime = NodeFactory.create("cc", config)
```

#### 2.5.3 CC 节点实现（智能体）

##### **cc/runtime.py - CC 节点运行时**

```python
class CCNodeRuntime(NodeRuntime):
    """Claude Code 节点的运行时实现"""
    
    组成:
    - client: MeshClient (事件系统接口)
    - hook_handler: HookHandler (处理 Claude Code Hooks)
    - event_processor: CCEventProcessor (处理入站事件)
    - mcp_server: MCPServer (提供 MCP 工具)
    - session_manager: CCSessionManager (会话管理)
    
    职责:
    1. 注册 Claude Code Hooks
    2. 启动 MCP 工具服务器
    3. 监听 Inbox，处理入站事件
    4. 产生出站事件（通过 Hook）
    
    生命周期:
    async def start():
        1. 注册 Hooks
        2. 启动 MCP Server
        3. 启动事件处理循环
    
    async def event_loop():
        async for envelope in client.inbox:
            await event_processor.process(envelope.event)
            await envelope.ack()
```

##### **cc/hook_handler.py - Hook 处理**

```python
class HookHandler:
    """处理 Claude Code 的 Hook 事件"""
    
    职责:
    - 捕获 Claude 的生命周期回调
    - 转换为 MeshEvent
    - 判断是否阻塞订阅
    - 发送事件并等待回复（如果阻塞）
    - 聚合多订阅者的回复
    
    主要方法:
    - handle_pre_tool_use(context: HookContext) -> HookResult
      1. 创建 PreToolUseEvent
      2. 查询是否有阻塞订阅者
      3. 如果有，调用 outbox.send_blocking()
      4. 聚合回复，返回 allow/deny/ask
      5. 如果没有，调用 outbox.send()，返回 allow
    
    - handle_post_tool_use(context) -> HookResult
    - handle_user_prompt_submit(context) -> HookResult
    - ...
    
    - aggregate_decisions(replies: List[Any]) -> Decision
      一票否决制：任何 deny → 拒绝，任何 ask → 询问，全部 allow → 允许
```

##### **cc/event_processor.py - 事件处理**

```python
class CCEventProcessor:
    """CC 节点的事件处理器"""
    
    职责:
    - 将接收到的 MeshEvent 路由到正确的会话
    - 格式化事件为 Claude 可理解的消息
    
    组成:
    - session_manager: CCSessionManager
    - session_resolver: CCSessionResolver
    
    流程:
    async def process(event: MeshEvent):
        1. 获取订阅关系（包含 session_scope 配置）
        2. 使用 SessionResolver 计算 session_id
        3. 使用 SessionManager 获取或创建 Session
        4. 格式化事件为消息
        5. 发送消息到 Session
    
    关键点:
    - 使用 session_scope 决定会话粒度
    - 如果上游没有 session_trace（如 Scheduler），创建新会话
```

##### **cc/session/ - 会话管理（CC 特有）**

**重要**: 这是 CC 节点如何组织内部状态的实现细节，不是事件系统的一部分。

```python
# cc/session/resolver.py
class CCSessionResolver:
    """CC 节点的会话解析器"""
    
    职责:
    - 根据 SessionTrace 和 Session Scope 计算 session_id
    - 这是 CC 节点特有的逻辑，其他节点可能不需要
    
    方法:
    - resolve_session_id(event, session_scope, session_filter) -> str
      
      根据策略计算:
      - "upstream-session": f"{trace.node_id}:{trace.upstream_session_id}"
      - "per-event": event.event_id
      - "global": "global:global"
      - "random/round-robin/load-balanced": 委托给 SessionManager

# cc/session/manager.py
class CCSessionManager:
    """CC 节点的会话管理器"""
    
    职责:
    - 管理 Backend Session（内部会话）
    - 管理 Interactive Agent（外部进程）
    - 实现派发型策略（random/round-robin/load-balanced）
    
    数据:
    - backend_sessions: Dict[str, CCBackendSession]
    - interactive_agents: Dict[str, InteractiveAgentProxy]
    
    方法:
    - get_or_create(session_id: str) -> Session
      1. 检查是否有 Interactive Agent 占据该 session_id
      2. 如果有，返回 Interactive Agent
      3. 否则，获取或创建 Backend Session
    
    - select_session_by_strategy(strategy, filter_type) -> Session
      实现派发型策略（从现有会话中选择）

# cc/session/backend_session.py
class CCBackendSession:
    """CC 的 Backend Session（使用 claude-agent-sdk）"""
    
    职责:
    - 在 Node Runtime 内部运行的会话
    - 轻量级，适合高并发
    
    实现:
    - 使用 claude-agent-sdk 创建会话
    - 维护消息历史
    - 调用 Claude API
    
    特点:
    - 非独立进程
    - 由 SessionManager 管理生命周期
    - pending_events_count（用于负载均衡）

# cc/session/interactive_proxy.py
class InteractiveAgentProxy:
    """外部 Claude Code 进程的代理"""
    
    职责:
    - 代表用户启动的 Claude Code 进程
    - 通过 IPC 与 Node Runtime 通信
    
    实现:
    - 持有 IPC 连接（UDS 或其他）
    - 将事件通过 IPC 投递给外部进程
    
    特点:
    - 独立进程（用户可见）
    - 可以"占据"某个 session_id
    - 用户控制生命周期

# cc/session/strategies.py
class SessionScopeStrategy:
    """Session Scope 策略实现"""
    
    CreationStrategy: 根据规则创建/复用会话
    - upstream-session
    - per-event
    - upstream-node
    - global
    
    DispatchStrategy: 从现有会话中选择
    - random
    - round-robin
    - load-balanced
    - sticky-source
```

##### **cc/mcp_server.py - MCP 工具**

```python
class MCPServer:
    """为 Claude 提供 MCP 工具"""
    
    提供的工具:
    - respond_to_pre_tool_use(event_id, decision, reason)
      回复阻塞的 PreToolUse 事件
    
    - respond_to_post_tool_use(event_id, content)
      回复 PostToolUse 事件（如果是阻塞订阅）
    
    - send_message_to_node(target_id, content)
      主动发送消息给其他节点
    
    实现:
    - 通过 Node Runtime 的 outbox 发送 NodeMessage
    - reply_to 字段指向原事件 ID
    - 触发发送方的 Waiter
```

#### 2.5.4 非智能体节点示例

##### **scheduler/runtime.py - 调度器节点**

```python
class SchedulerNodeRuntime(NodeRuntime):
    """调度器节点：定时产生事件"""
    
    特点:
    - 完全不需要 Session 的概念
    - 没有 session/ 子目录
    - 不处理 session_scope 配置（忽略即可）
    
    实现:
    async def start():
        while True:
            await asyncio.sleep(interval)
            
            event = ScheduleEvent(
                source_id=self.node_id,
                schedule_time=datetime.now(),
                session_trace=None  # 调度器没有会话概念
            )
            
            await self.client.outbox.send(event)
    
    async def process_event(envelope):
        # 调度器通常不消费事件，可以为空
        pass
```

##### **webhook/runtime.py - Webhook 节点**

```python
class WebhookNodeRuntime(NodeRuntime):
    """Webhook 节点：HTTP 请求转事件"""
    
    特点:
    - 完全不需要 Session 的概念
    - 没有 session/ 子目录
    
    实现:
    async def start():
        # 启动 HTTP 服务器
        app = create_http_server()
        app.add_route("/webhook", self.handle_webhook)
    
    async def handle_webhook(request):
        event = WebhookEvent(
            source_id=self.node_id,
            payload=request.body,
            session_trace=None  # Webhook 没有会话概念
        )
        
        await self.client.outbox.send(event)
```

#### 2.5.5 关键设计点

1. **Session 仅存在于智能体节点**:
   - CC 节点有 `session/` 子目录
   - Scheduler/Webhook 节点没有 `session/` 子目录
   - 非智能体节点的 `session_trace` 可以为 `None`

2. **插件化架构**:
   - 通过 `NodeFactory` 注册节点类型
   - 新增节点类型只需添加子目录

3. **统一接口**:
   - 所有节点实现 `NodeRuntime` 接口
   - 对事件系统来说，不同节点类型没有区别

---

### 2.6 `mosaic.daemon` - Daemon 进程

**职责**: Mesh 实例的守护进程，负责监控和管理 Node Runtime

#### 2.6.1 目录结构

```
daemon/
├── __init__.py
├── daemon.py                # MosaicDaemon 主类
├── process_monitor.py       # 进程监控
├── restart_manager.py       # 重启管理
├── control_server.py        # 控制接口（UDS Server）
├── metrics.py               # 监控指标
└── alerts.py                # 告警管理
```

#### 2.6.2 提供的功能

##### **daemon.py - 主类**

```python
class MosaicDaemon:
    """Mesh 的守护进程"""
    
    职责:
    - 管理 Mesh 内所有 Node Runtime 进程的生命周期
    - 监控进程健康状态
    - 自动重启崩溃的进程
    - 提供控制接口（启动/停止节点）
    
    组成:
    - process_monitor: ProcessMonitor
    - restart_manager: RestartManager
    - control_server: DaemonControlServer
    - node_registry: Dict[str, NodeInfo]
    
    生命周期:
    async def start():
        1. 启动控制服务器（UDS）
        2. 启动进程监控循环
        3. 恢复之前运行的节点（如果配置了自动重启）
    
    async def shutdown():
        1. 停止接收新请求
        2. 通知所有节点准备退出
        3. 等待节点优雅退出（超时 30 秒）
        4. 强制终止未退出的节点
        5. 清理资源
```

##### **process_monitor.py - 进程监控**

```python
class ProcessMonitor:
    """监控节点进程的存活状态"""
    
    监控方式:
    1. 主监控：PID 检测（os.kill(pid, 0)）
    2. 辅助监控：心跳机制（可选，检测僵尸进程）
    
    监控频率: 每秒检查一次
    
    方法:
    - monitor_loop() -> None
      主监控循环，定期检查所有节点进程
    
    - is_process_alive(pid: int) -> bool
      检查进程是否存活
    
    - on_process_died(node_id: str) -> None
      进程死亡回调，触发重启逻辑

class HeartbeatMonitor:
    """基于心跳的监控（可选）"""
    
    职责:
    - 检测僵尸进程（进程存在但卡住）
    - 节点定期发送心跳
    - 超时判定为卡住，触发重启
```

##### **restart_manager.py - 重启管理**

```python
class RestartManager:
    """管理节点重启策略"""
    
    重启策略:
    - mode: "always" | "on-failure" | "no"
    - max_retries: int (默认 3)
    - backoff_strategy: "exponential" (默认)
    - backoff_seconds: float (基础退避时间)
    
    方法:
    - on_process_died(node_id, info) -> None
      1. 检查重启策略（mode）
      2. 检查重试次数（crash_count vs max_retries）
      3. 计算退避时间（指数退避，最多 5 分钟）
      4. 等待退避时间
      5. 重启节点
    
    - calculate_backoff(crash_count, base) -> float
      指数退避：min(base * (2 ** crash_count), 300)
```

##### **control_server.py - 控制接口**

```python
class DaemonControlServer:
    """Daemon 的控制接口（UDS Server）"""
    
    Socket 路径: ~/.mosaic/<mesh_id>/daemon.sock
    
    提供的命令:
    - start_node(node_id) -> None
    - stop_node(node_id) -> None
    - restart_node(node_id) -> None
    - get_status(node_id) -> NodeStatus
    - list_nodes() -> List[NodeStatus]
    
    CLI 通过此接口与 Daemon 通信
```

##### **metrics.py - 监控指标**

```python
class MetricsCollector:
    """收集系统指标"""
    
    Daemon 级别指标:
    - nodes_total: 节点总数
    - nodes_running: 运行中的节点
    - nodes_failed: 失败的节点
    - uptime_seconds: Daemon 运行时间
    
    Node 级别指标:
    - status: running/failed/stopped
    - crash_count: 崩溃次数
    - uptime_seconds: 节点运行时间
    - last_restart: 最后一次重启时间
    - pending_events: 待处理事件数
```

#### 2.6.3 关键设计点

1. **systemd 集成**: 
   - 生产环境通过 systemd 管理 Daemon
   - 开发环境自动恢复机制

2. **可靠性保障**:
   - PID 检测 + 可选心跳
   - 指数退避重启
   - 最大重试限制

3. **优雅退出**:
   - 通知节点准备退出
   - 等待优雅退出（超时）
   - 强制终止

---

### 2.7 `mosaic.cli` - 命令行工具

**职责**: 用户交互的主要入口

#### 2.7.1 目录结构

```
cli/
├── __init__.py
├── main.py                  # 主入口（Click）
├── commands/                # 命令组
│   ├── __init__.py
│   ├── mesh.py              # mosaic init, reset
│   ├── node.py              # mosaic create, run, program
│   ├── subscription.py      # mosaic sub, unsub
│   ├── daemon.py            # mosaic daemon start/stop/status
│   ├── info.py              # mosaic ps, status, list
│   └── debug.py             # mosaic logs, history
├── interactive.py           # mosaic chat (启动 Interactive Agent)
├── output.py                # Rich 格式化输出
└── validation.py            # 参数验证
```

#### 2.7.2 主要命令

```bash
# Mesh 管理
mosaic init --mesh-id dev-mesh
mosaic reset

# 节点管理
mosaic create worker --path ./worker --type cc
mosaic config worker set restart-policy always
mosaic config worker set max-retries 5

# 订阅关系
mosaic sub auditor worker "!PreToolUse" --session-scope upstream-session
mosaic sub logger worker "*" --session-scope round-robin --session-filter backend-only
mosaic unsub auditor worker "!PreToolUse"

# Daemon 管理
mosaic daemon start
mosaic daemon stop
mosaic daemon status

# 节点运行
mosaic run worker           # 启动为前端（Interactive）
mosaic start logger         # 启动为后台（Backend）
mosaic program auditor      # 编程模式（培训）
mosaic chat worker          # 连接到 Interactive Agent

# 信息查询
mosaic ps                   # 列出所有节点状态
mosaic status worker        # 查看节点详细状态
mosaic list                 # 列出节点和订阅关系
mosaic topology             # 查看拓扑图

# 调试
mosaic logs worker --tail 100 --follow
mosaic history worker       # 崩溃历史
```

#### 2.7.3 关键设计点

1. **Click 框架**: 
   - 命令组织清晰
   - 自动生成帮助信息

2. **Rich 输出**: 
   - 表格、树形结构、进度条
   - 拓扑可视化

3. **参数验证**: 
   - 统一的验证逻辑
   - 友好的错误提示

---

### 2.8 `mosaic.utils` - 工具库

**职责**: 提供通用工具函数

#### 2.8.1 目录结构

```
utils/
├── __init__.py
├── id_generator.py          # ID 生成
├── serialization.py         # 事件序列化
├── logging.py               # 日志配置
├── paths.py                 # 路径管理
└── validation.py            # 通用验证
```

#### 2.8.2 提供的工具

```python
# id_generator.py
- generate_event_id() -> str
- generate_session_id() -> str
- generate_mesh_id() -> str

# serialization.py
- serialize_event(event: MeshEvent) -> str
- deserialize_event(data: str) -> MeshEvent
- 支持 JSON 和 XML 格式

# paths.py
- get_mesh_dir(mesh_id: str) -> Path
  返回: ~/.mosaic/<mesh_id>/
- get_socket_path(mesh_id: str, node_id: str) -> Path
  返回: ~/.mosaic/<mesh_id>/sockets/<node_id>.sock
- get_daemon_socket(mesh_id: str) -> Path
- get_database_path() -> Path

# logging.py
- configure_logging(level: str, format: str)
- get_logger(name: str) -> Logger
```

---

## 3. 模块依赖关系

### 3.1 依赖图

```
┌─────────────────────────────────────────────────────────┐
│                        cli                              │  用户入口
└────────────┬────────────────────────────────────────────┘
             │
             ↓
┌────────────┴────────────┐        ┌──────────────────┐
│        daemon           │        │      nodes       │
│   (进程管理和监控)        │        │  (节点类型实现)   │
└────────────┬────────────┘        └────────┬─────────┘
             │                              │
             ↓                              ↓
┌────────────┴──────────────────────────────┴─────────────┐
│                      runtime                            │  运行时基础设施
│  (MeshClient/WaiterRegistry/EventRouter)               │
└────────────┬──────────────┬─────────────────────────────┘
             │              │
             ↓              ↓
┌────────────┴────────┐  ┌─┴─────────────────────────────┐
│      transport      │  │         storage               │
│   (传输层实现)       │  │  (控制平面持久化)              │
│                     │  │  - 节点定义                    │
│  - 事件存储(内部)    │  │  - 订阅关系                    │
│  - SQLite: DB      │  │  - Mesh 配置                   │
│  - Kafka: Topic    │  │                               │
│  - Redis: Stream   │  │  不包含事件存储                 │
└────────────┬────────┘  └─┬─────────────────────────────┘
             │              │
             ↓              ↓
┌────────────┴──────────────┴──────────────────────────────┐
│                        core                              │  核心抽象
│         (接口定义、数据模型、类型系统)                      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                        utils                             │  工具库
│              (所有模块都可以依赖)                          │
└──────────────────────────────────────────────────────────┘
```

### 3.1.1 两个持久化层次

```
持久化层次:

1. 控制平面（storage 模块）
   数据库: ~/.mosaic/control.db
   内容: 节点定义、订阅关系、Mesh 配置
   特点: 与传输实现无关，系统配置数据

2. 数据平面（transport 模块内部）
   SQLite:  ~/.mosaic/<mesh_id>/events.db
   Kafka:   Topic: mosaic-<mesh_id>-events
   Redis:   Stream: mosaic:<mesh_id>:events
   内容: 事件队列
   特点: 传输层的实现细节，不同传输方式不同
```

### 3.2 依赖规则表

| 模块 | 可以依赖 | 不能依赖 | 说明 |
|------|---------|---------|------|
| `core` | 无 | 所有其他模块 | 基础抽象层 |
| `utils` | 无 | 所有其他模块 | 工具库 |
| `transport` | core, utils | storage, runtime, nodes, daemon, cli | 传输层（内部管理事件存储） |
| `storage` | core, utils | transport, runtime, nodes, daemon, cli | 控制平面持久化 |
| `runtime` | core, transport, storage, utils | nodes, daemon, cli | 运行时基础设施 |
| `nodes` | core, runtime, utils | transport, storage, daemon, cli | 节点实现（通过 runtime 使用传输） |
| `daemon` | core, runtime, storage, utils | transport, nodes, cli | 进程管理 |
| `cli` | 所有模块 | 无 | 用户入口 |

**关键约束**:
- 单向依赖（从上到下）
- 禁止循环依赖
- `core` 和 `utils` 是基础层，不依赖任何业务模块
- **`transport` 和 `storage` 是平行的，互不依赖**
  - `transport`: 管理事件数据（数据平面）
  - `storage`: 管理元数据（控制平面）
- `nodes` 不直接依赖 `transport` 和 `storage`，通过 `runtime` 间接使用

### 3.3 详细依赖关系分析

#### 3.3.1 基础层（无依赖）

##### **`core` - 零依赖的抽象层**

```python
# core 模块不导入任何业务模块
from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel

# 只定义接口和数据模型
class MeshClient(ABC):
    ...
```

**为什么零依赖**:
- 作为所有模块的基础契约
- 保证接口定义的稳定性
- 避免循环依赖的起点

**被谁依赖**: 所有其他模块

##### **`utils` - 纯工具函数**

```python
# utils 模块只提供工具函数
import uuid
from pathlib import Path

def generate_event_id() -> str:
    return f"evt-{uuid.uuid4().hex[:12]}"

def get_mesh_dir(mesh_id: str) -> Path:
    return Path.home() / ".mosaic" / mesh_id
```

**为什么零依赖**:
- 工具函数不应依赖业务逻辑
- 可以被任何模块安全使用

**被谁依赖**: 所有其他模块

---

#### 3.3.2 数据层（依赖基础层）

##### **`storage` - 控制平面持久化**

```python
# storage 依赖 core 和 utils
from mosaic.core.models import Node, Subscription
from mosaic.utils.paths import get_control_db_path

class NodeRepository:
    def __init__(self):
        self.db_path = get_control_db_path()
    
    async def create(self, node: Node) -> None:
        # 存储节点定义
        pass
```

**依赖关系**:
```
storage
  ├─→ core (使用数据模型: Node, Subscription, Mesh)
  └─→ utils (使用路径工具: get_control_db_path)
```

**为什么依赖 core**: 
- 需要 `Node`, `Subscription` 等数据模型
- 需要知道数据结构的定义

**为什么依赖 utils**:
- 需要路径管理工具
- 需要 ID 生成工具

**不依赖其他模块**:
- `storage` 是纯数据访问层
- 不需要知道运行时逻辑
- 不需要知道事件如何传输

**被谁依赖**: runtime, daemon, cli

##### **`transport` - 数据平面传输**

```python
# transport 依赖 core 和 utils
from mosaic.core.interfaces import TransportBackend
from mosaic.core.models import MeshEvent, EventEnvelope
from mosaic.utils.serialization import serialize_event

class SQLiteTransportBackend(TransportBackend):
    async def send_event(self, event: MeshEvent) -> None:
        # 序列化并存储事件
        payload = serialize_event(event)
        await self._save_to_db(payload)
```

**依赖关系**:
```
transport
  ├─→ core (实现接口: TransportBackend, 使用模型: MeshEvent)
  └─→ utils (使用序列化: serialize_event, 路径: get_mesh_dir)
```

**为什么依赖 core**:
- 需要实现 `TransportBackend` 接口
- 需要处理 `MeshEvent` 数据模型

**为什么依赖 utils**:
- 需要事件序列化
- 需要路径管理

**不依赖其他模块**:
- `transport` 是独立的传输层
- 内部管理事件存储（EventRepository 是内部实现）
- 不需要知道控制平面的数据

**被谁依赖**: runtime

---

#### 3.3.3 运行时层（依赖数据层）

##### **`runtime` - 运行时基础设施**

```python
# runtime 依赖 core, transport, storage, utils
from mosaic.core.interfaces import MeshClient, MeshInbox, MeshOutbox
from mosaic.transport.base import TransportBackend
from mosaic.storage.repositories import SubscriptionRepository
from mosaic.utils.id_generator import generate_event_id

class MeshClientImpl(MeshClient):
    def __init__(
        self,
        transport: TransportBackend,        # 来自 transport 模块
        subscription_repo: SubscriptionRepository  # 来自 storage 模块
    ):
        self.transport = transport
        self.subscription_repo = subscription_repo
        self.waiter_registry = WaiterRegistry()
```

**依赖关系**:
```
runtime
  ├─→ core (实现接口: MeshClient, MeshInbox, MeshOutbox)
  ├─→ transport (使用: TransportBackend 接口)
  ├─→ storage (使用: SubscriptionRepository, NodeRepository)
  └─→ utils (使用: ID 生成, 序列化)
```

**为什么依赖 core**:
- 需要实现 `MeshClient` 等接口

**为什么依赖 transport**:
- 需要通过传输层发送和接收事件
- 依赖注入 `TransportBackend` 实例

**为什么依赖 storage**:
- 需要查询订阅关系（路由事件）
- 需要查询节点配置

**为什么依赖 utils**:
- 需要生成 event_id
- 需要路径管理

**关键设计**:
```python
# EventRouter 需要查询订阅关系
class EventRouter:
    def __init__(self, subscription_repo: SubscriptionRepository):
        self.subscription_repo = subscription_repo
    
    async def route_event(self, event: MeshEvent):
        # 查询控制平面：谁订阅了这个节点
        subscriptions = await self.subscription_repo.get_by_target(
            mesh_id=event.mesh_id,
            target_id=event.source_id
        )
        
        for sub in subscriptions:
            # 通过 transport 发送
            routed_event = event.clone()
            routed_event.target_id = sub.source_id
            await self.transport.send_event(routed_event)
```

**不依赖其他模块**:
- 不依赖 `nodes`（节点类型是插件）
- 不依赖 `daemon`（进程管理是独立的）
- 不依赖 `cli`（CLI 是上层）

**被谁依赖**: nodes, daemon

---

#### 3.3.4 节点实现层（依赖运行时）

##### **`nodes` - 节点类型实现**

```python
# nodes 依赖 core, runtime, utils
from mosaic.core.interfaces import MeshClient
from mosaic.runtime.waiter import WaiterRegistry
from mosaic.utils.logging import get_logger

class CCNodeRuntime(NodeRuntime):
    def __init__(self, client: MeshClient):
        self.client = client  # 来自 runtime 模块
        self.logger = get_logger(__name__)
    
    async def start(self):
        # 通过 client.inbox 接收事件
        async for envelope in self.client.inbox:
            await self.process_event(envelope.event)
            await envelope.ack()
    
    async def send_hook_event(self, event: MeshEvent):
        # 通过 client.outbox 发送事件
        await self.client.outbox.send(event)
```

**依赖关系**:
```
nodes
  ├─→ core (使用模型: MeshEvent, 使用接口: NodeRuntime)
  ├─→ runtime (使用: MeshClient, WaiterRegistry)
  └─→ utils (使用: 日志, ID 生成)
```

**为什么依赖 core**:
- 需要实现 `NodeRuntime` 接口
- 需要创建和处理 `MeshEvent`

**为什么依赖 runtime**:
- 需要 `MeshClient` 来收发事件
- 需要 `WaiterRegistry` 处理阻塞事件

**为什么依赖 utils**:
- 需要日志工具
- 需要 ID 生成

**不直接依赖 transport 和 storage**:
```python
# ✗ 错误：节点不应直接依赖传输层
from mosaic.transport.sqlite import SQLiteTransportBackend

# ✓ 正确：通过 MeshClient 间接使用
class CCNodeRuntime:
    def __init__(self, client: MeshClient):
        self.client = client
        # client 内部已经封装了 transport
```

**关键设计**:
- 节点通过 `MeshClient` 抽象接口与系统交互
- 不需要知道底层传输实现（SQLite/Kafka/Redis）
- 不需要直接访问控制平面数据库

**被谁依赖**: cli

---

#### 3.3.5 进程管理层（依赖运行时和存储）

##### **`daemon` - Daemon 进程**

```python
# daemon 依赖 core, runtime, storage, utils
from mosaic.core.types import RestartPolicy
from mosaic.runtime.client import MeshClientImpl
from mosaic.storage.repositories import NodeRepository
from mosaic.utils.paths import get_mesh_dir

class MosaicDaemon:
    def __init__(self, mesh_id: str):
        self.mesh_id = mesh_id
        self.node_repo = NodeRepository()  # 查询节点配置
    
    async def start_node(self, node_id: str):
        # 1. 从控制平面获取节点配置
        node = await self.node_repo.get(self.mesh_id, node_id)
        
        # 2. 创建节点进程
        process = await self._spawn_node_process(node)
        
        # 3. 监控进程
        await self.process_monitor.watch(process)
```

**依赖关系**:
```
daemon
  ├─→ core (使用模型: Node, RestartPolicy)
  ├─→ runtime (创建: MeshClient 实例)
  ├─→ storage (查询: NodeRepository)
  └─→ utils (使用: 路径管理, 日志)
```

**为什么依赖 core**:
- 需要 `Node` 数据模型
- 需要 `RestartPolicy` 类型

**为什么依赖 runtime**:
- 需要为节点进程创建 `MeshClient` 实例

**为什么依赖 storage**:
- 需要查询节点配置（类型、工作区、重启策略）

**为什么依赖 utils**:
- 需要路径管理（PID 文件、Socket 路径）
- 需要日志工具

**不依赖 transport**:
- Daemon 不直接操作事件传输
- 传输由节点进程内部的 runtime 处理

**不依赖 nodes**:
- Daemon 通过 subprocess 启动节点进程
- 不需要知道节点的具体实现

**被谁依赖**: cli

---

#### 3.3.6 用户界面层（依赖所有模块）

##### **`cli` - 命令行工具**

```python
# cli 可以依赖所有模块
from mosaic.core.models import Node, Subscription
from mosaic.storage.repositories import NodeRepository, SubscriptionRepository
from mosaic.daemon.daemon import MosaicDaemon
from mosaic.nodes.base import NodeFactory
from mosaic.runtime.admin import MeshAdminImpl
from mosaic.utils.output import TableFormatter

@click.command()
def create_node(node_id: str, node_type: str):
    # 使用 storage 创建节点
    node_repo = NodeRepository()
    node = Node(node_id=node_id, node_type=node_type, ...)
    await node_repo.create(node)
    
    # 使用 daemon 启动节点
    daemon = MosaicDaemon.connect()
    await daemon.start_node(node_id)

@click.command()
def subscribe(source: str, target: str, pattern: str):
    # 使用 storage 创建订阅
    sub_repo = SubscriptionRepository()
    subscription = Subscription(...)
    await sub_repo.create(subscription)
```

**依赖关系**:
```
cli
  ├─→ core (使用所有数据模型)
  ├─→ storage (直接操作 Repository)
  ├─→ daemon (控制进程生命周期)
  ├─→ nodes (查询节点类型)
  ├─→ runtime (创建 MeshAdmin)
  ├─→ transport (配置传输后端)
  └─→ utils (格式化输出, 路径管理)
```

**为什么依赖所有模块**:
- CLI 是用户交互的入口
- 需要调用各个模块的功能
- 作为系统的"胶水层"

**不被谁依赖**: 无（CLI 是最上层）

---

### 3.4 依赖链示例

#### 3.4.1 事件发送流程的依赖链

```
用户操作 (CLI)
  ↓ 调用
Daemon
  ↓ 启动
Node Runtime (nodes.cc)
  ↓ 使用
MeshClient (runtime.client)
  ↓ 使用
MeshOutbox (runtime)
  ↓ 使用
TransportBackend (transport.sqlite)
  ↓ 写入
Events Database (transport 内部)
```

**依赖模块顺序**: cli → daemon → nodes → runtime → transport

#### 3.4.2 事件路由流程的依赖链

```
TransportBackend (transport.sqlite)
  ↓ 提供事件给
MeshInbox (runtime)
  ↓ 查询订阅关系
SubscriptionRepository (storage)
  ↓ 读取
Control Database
```

**依赖模块顺序**: transport → runtime → storage

**关键点**: 
- 数据平面（transport）和控制平面（storage）通过 runtime 协作
- runtime 是桥梁，协调两个平行的数据层

#### 3.4.3 节点启动流程的依赖链

```
CLI Command (cli.commands.node)
  ↓ 调用
MosaicDaemon (daemon)
  ↓ 查询节点配置
NodeRepository (storage)
  ↓ 创建运行时
MeshClientImpl (runtime)
  ↓ 注入传输层
TransportBackend (transport)
  ↓ 创建节点实例
NodeFactory (nodes.base)
  ↓ 实例化
CCNodeRuntime (nodes.cc)
```

**依赖模块顺序**: cli → daemon → storage → runtime → transport → nodes

---

### 3.5 依赖约束和最佳实践

#### 3.5.1 禁止的依赖模式

##### **❌ 循环依赖**

```python
# ✗ 错误：transport 不能依赖 runtime
# transport/sqlite/backend.py
from mosaic.runtime.waiter import WaiterRegistry  # 禁止！

class SQLiteTransportBackend:
    def __init__(self):
        self.waiter = WaiterRegistry()  # 破坏了层次
```

**为什么禁止**: 
- 会导致模块无法独立编译
- 破坏了分层架构

**正确做法**:
```python
# ✓ 正确：runtime 依赖 transport
# runtime/client.py
from mosaic.transport.base import TransportBackend

class MeshClientImpl:
    def __init__(self, transport: TransportBackend):
        self.transport = transport
        self.waiter = WaiterRegistry()  # 在 runtime 中创建
```

##### **❌ 节点直接依赖传输层**

```python
# ✗ 错误：nodes 不能直接依赖 transport
# nodes/cc/runtime.py
from mosaic.transport.sqlite import SQLiteTransportBackend

class CCNodeRuntime:
    def __init__(self):
        self.transport = SQLiteTransportBackend()  # 破坏了抽象
```

**为什么禁止**:
- 破坏了抽象层次
- 节点与传输实现强耦合
- 无法切换传输后端

**正确做法**:
```python
# ✓ 正确：通过 MeshClient 抽象
# nodes/cc/runtime.py
from mosaic.core.interfaces import MeshClient

class CCNodeRuntime:
    def __init__(self, client: MeshClient):
        self.client = client  # 不知道底层是 SQLite 还是 Kafka
```

##### **❌ 存储层依赖传输层**

```python
# ✗ 错误：storage 不能依赖 transport
# storage/repositories/node_repo.py
from mosaic.transport.sqlite import SQLiteTransportBackend

class NodeRepository:
    def __init__(self):
        self.transport = SQLiteTransportBackend()  # 错误的依赖
```

**为什么禁止**:
- 两者是平行的数据层
- 控制平面和数据平面应该独立

#### 3.5.2 推荐的依赖模式

##### **✓ 依赖注入**

```python
# ✓ 推荐：通过构造函数注入依赖
class MeshClientImpl:
    def __init__(
        self,
        transport: TransportBackend,        # 注入
        subscription_repo: SubscriptionRepository  # 注入
    ):
        self.transport = transport
        self.subscription_repo = subscription_repo
```

**优势**:
- 松耦合
- 易于测试（可以 mock）
- 支持多种实现

##### **✓ 依赖抽象而非具体实现**

```python
# ✓ 推荐：依赖接口
from mosaic.core.interfaces import TransportBackend  # 抽象

# ✗ 避免：依赖具体实现
from mosaic.transport.sqlite import SQLiteTransportBackend  # 具体类
```

##### **✓ 通过中间层协调**

```python
# ✓ 推荐：runtime 协调 transport 和 storage
class EventRouter:
    def __init__(
        self,
        transport: TransportBackend,        # 数据平面
        subscription_repo: SubscriptionRepository  # 控制平面
    ):
        self.transport = transport
        self.subscription_repo = subscription_repo
    
    async def route(self, event: MeshEvent):
        # 查询控制平面
        subscriptions = await self.subscription_repo.get_by_target(...)
        
        # 使用数据平面发送
        for sub in subscriptions:
            await self.transport.send_event(...)
```

---

### 3.6 依赖验证清单

开发时可以用这个清单验证依赖是否合理：

#### **检查点 1: 分层检查**

```
Layer 0: core, utils (基础层)
  ↓
Layer 1: transport, storage (数据层，平行)
  ↓
Layer 2: runtime (运行时层)
  ↓
Layer 3: nodes, daemon (业务层)
  ↓
Layer 4: cli (界面层)
```

- [ ] 每个模块只依赖同层或下层模块
- [ ] 没有向上的依赖

#### **检查点 2: 平行层检查**

- [ ] `transport` 不依赖 `storage`
- [ ] `storage` 不依赖 `transport`
- [ ] `nodes` 不依赖 `daemon`
- [ ] `daemon` 不依赖 `nodes`

#### **检查点 3: 抽象检查**

- [ ] 高层依赖抽象（core 中的接口）
- [ ] 不依赖具体实现类（除非必要）
- [ ] 使用依赖注入而非直接创建

#### **检查点 4: 循环依赖检查**

```bash
# 使用工具检测循环依赖
python -m pydeps mosaic --show-cycles
```

---

## 4. 持久化层次详解

### 4.1 为什么需要两个持久化层

Mosaic 系统有两类不同性质的数据，需要不同的存储策略：

#### **控制平面数据（元数据）**
- **内容**: 节点定义、订阅关系、Mesh 配置、节点能力
- **特点**: 
  - 数据量小
  - 变更频率低
  - 需要严格一致性
  - 与传输实现无关
- **存储**: `storage` 模块，统一使用 SQLite（`~/.mosaic/control.db`）
- **生命周期**: 长期存储，除非显式删除

#### **数据平面数据（事件）**
- **内容**: 事件队列、事件状态
- **特点**:
  - 数据量大
  - 高频写入
  - 需要高吞吐
  - 存储方式取决于传输实现
- **存储**: `transport` 模块内部实现
  - SQLite: `~/.mosaic/<mesh_id>/events.db`
  - Kafka: Topic `mosaic-<mesh_id>-events`
  - Redis: Stream `mosaic:<mesh_id>:events`
- **生命周期**: 短期存储，处理完成后可清理

### 4.2 架构优势

```
优势对比:

分离前（混淆）:
storage/
├── node_repo.py         ✓ 控制平面
├── subscription_repo.py ✓ 控制平面
└── event_repo.py        ✗ 数据平面（应该在 transport 中）

问题:
1. EventRepository 暴露给外部，破坏了传输层的封装
2. 切换传输后端（SQLite → Kafka）需要修改 storage 模块
3. 两类数据混在一起，职责不清

分离后（清晰）:
storage/                      transport/sqlite/
├── node_repo.py              ├── database.py (内部)
├── subscription_repo.py      └── repository.py (内部)
└── mesh_repo.py

优势:
1. 传输层完全封装，EventRepository 是内部实现
2. 切换传输后端（SQLite → Kafka）不影响 storage
3. 职责清晰，数据平面和控制平面分离
```

### 4.3 数据库路径规划

```
~/.mosaic/
├── control.db               # 控制平面（storage 模块）
│                            # 表: meshes, nodes, subscriptions
│
├── mesh-1/                  # Mesh 实例目录
│   ├── events.db            # 数据平面（transport.sqlite）
│   │                        # 表: event_queue
│   ├── daemon.pid
│   ├── daemon.sock
│   └── sockets/
│       ├── node-1.sock
│       └── node-2.sock
│
└── mesh-2/                  # 另一个 Mesh 实例
    ├── events.db
    └── ...
```

**关键点**:
- **control.db**: 全局唯一，所有 Mesh 共享（通过 mesh_id 隔离）
- **events.db**: 每个 Mesh 独立，由该 Mesh 的传输层管理
- 控制平面和数据平面的数据库物理分离

### 4.4 代码示例

#### **控制平面：查询订阅关系**

```python
# 在 runtime/event_router.py 中
from mosaic.storage.repositories import SubscriptionRepository

class EventRouter:
    def __init__(self, subscription_repo: SubscriptionRepository):
        self.subscription_repo = subscription_repo
    
    async def route_event(self, event: MeshEvent):
        # 查询控制平面：谁订阅了这个节点
        subscriptions = await self.subscription_repo.get_by_target(
            mesh_id=event.mesh_id,
            target_id=event.source_id
        )
        
        for sub in subscriptions:
            # 路由事件...
            pass
```

#### **数据平面：存储事件（内部实现）**

```python
# 在 transport/sqlite/backend.py 中
from .repository import EventRepository  # 内部导入

class SQLiteTransportBackend(TransportBackend):
    def __init__(self, mesh_id: str):
        self.mesh_id = mesh_id
        # EventRepository 是内部实现，不暴露给外部
        self._event_repo = EventRepository(f"~/.mosaic/{mesh_id}/events.db")
    
    async def send_event(self, event: MeshEvent):
        # 使用内部 EventRepository
        await self._event_repo.save(event)
        # 通过 UDS 通知
        await self.signal_client.notify(event.target_id)
```

**关键点**:
- `SubscriptionRepository` 是公开的 API（从 `storage` 导入）
- `EventRepository` 是内部实现（从 `transport.sqlite` 内部导入）
- 外部代码（`runtime`, `nodes`）不能直接访问 `EventRepository`

---

## 5. 扩展性设计

### 4.1 新增节点类型

步骤:
1. 在 `nodes/` 下创建子目录（如 `nodes/gemini/`）
2. 实现 `NodeRuntime` 接口
3. 如果是智能体节点，可以实现自己的 `session/` 子模块
4. 通过 `NodeFactory.register()` 注册

示例:
```python
# nodes/gemini/runtime.py
class GeminiNodeRuntime(NodeRuntime):
    async def start(self):
        # 启动 Gemini 节点
        pass
    
    async def process_event(self, envelope):
        # Gemini 的事件处理逻辑
        pass

# 注册
NodeFactory.register("gemini", GeminiNodeRuntime)
```

### 4.2 新增传输后端

步骤:
1. 在 `transport/` 下创建子目录（如 `transport/kafka/`）
2. 实现 `TransportBackend` 接口
3. 在配置中指定传输后端

示例:
```python
# transport/kafka/backend.py
class KafkaTransportBackend(TransportBackend):
    async def send_event(self, event):
        # 发送到 Kafka
        pass
    
    async def receive_events(self, node_id):
        # 从 Kafka 消费
        pass

# 使用
transport = KafkaTransportBackend(bootstrap_servers="localhost:9092")
client = MeshClientImpl(transport=transport, ...)
```

### 4.3 新增 Session Scope 策略

步骤:
1. 在 `nodes/cc/session/strategies.py` 中添加策略
2. 在 `CCSessionResolver` 中添加解析逻辑

示例:
```python
# 新增策略: "time-based"（按时间窗口组织会话）
class TimeBasedStrategy:
    def resolve(self, event):
        window = datetime.now().strftime("%Y-%m-%d-%H")
        return f"time:{window}"

# 在 CCSessionResolver 中添加
elif session_scope == "time-based":
    return TimeBasedStrategy().resolve(event)
```

---

## 5. 开发指南

### 5.1 从哪里开始

推荐开发顺序:

1. **Phase 1: 核心抽象**
   - 实现 `core` 模块（接口定义）
   - 实现 `utils` 模块（工具函数）
   - 实现 `storage` 模块（数据访问）

2. **Phase 2: 传输层**
   - 实现 `transport.base`（抽象）
   - 实现 `transport.sqlite`（SQLite + UDS）

3. **Phase 3: 运行时**
   - 实现 `runtime` 模块（组装器、Waiter、Router）

4. **Phase 4: CC 节点**
   - 实现 `nodes.cc`（最复杂，包含 Session 管理）

5. **Phase 5: Daemon 和 CLI**
   - 实现 `daemon`（进程管理）
   - 实现 `cli`（命令行工具）

6. **Phase 6: 其他节点类型**
   - 实现 `nodes.scheduler`
   - 实现 `nodes.webhook`

### 5.2 测试策略

```
tests/
├── unit/                    # 单元测试
│   ├── test_core/           # 测试核心抽象
│   ├── test_storage/        # 测试数据访问
│   ├── test_runtime/        # 测试运行时组件
│   └── test_nodes/          # 测试节点实现
├── integration/             # 集成测试
│   ├── test_event_flow.py   # 测试完整的事件流
│   ├── test_blocking.py     # 测试阻塞订阅
│   └── test_session_alignment.py  # 测试会话对齐
└── e2e/                     # 端到端测试
    ├── test_worker_auditor.py  # 测试审计场景
    └── test_crash_recovery.py  # 测试崩溃恢复
```

### 5.3 关键测试场景

1. **事件传输**: 发送事件 → 接收事件 → ACK
2. **阻塞订阅**: 发送阻塞事件 → 等待回复 → 聚合决策
3. **会话对齐**: 不同 Session Scope 的行为验证
4. **崩溃恢复**: 进程崩溃 → 事件重新可见 → 幂等处理
5. **多 Mesh 隔离**: 不同 Mesh 的事件不互相干扰

### 5.4 pyproject.toml 配置

```toml
[project]
name = "mosaic"
version = "0.1.0"
description = "Event-driven multi-agent collaboration mesh"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "aiosqlite>=0.19.0",
    # claude-agent-sdk (待确认包名)
]

[project.scripts]
mosaic = "mosaic.cli.main:cli"

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.5.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

**关键点**:
- **命令名称**: `mosaic`（而不是 ccm）
- **入口点**: `mosaic.cli.main:cli`
- **使用方式**: 用户通过 `mosaic` 命令与系统交互
- **Python 版本**: 要求 3.11+（支持新的类型系统特性）

---

## 6. 总结

### 6.1 关键设计决策

1. **抽象分层**: `core` 定义契约，实现与抽象分离
2. **传输可插拔**: 通过 `TransportBackend` 支持多种后端
3. **两个持久化层次**: 
   - **控制平面**（`storage`）: 元数据（节点、订阅、配置）
   - **数据平面**（`transport` 内部）: 事件存储（实现细节）
4. **Session 不是事件系统概念**: 仅存在于智能体节点
5. **节点类型插件化**: 通过 `NodeFactory` 注册和实例化
6. **单向依赖**: 严格控制依赖方向，避免循环

### 6.2 模块职责一览表

| 模块 | 核心职责 | 关键接口/组件 | 数据存储 |
|------|---------|--------------|---------|
| `core` | 定义接口契约 | interfaces.py: MeshClient, MeshInbox, MeshOutbox | 无 |
| `transport` | 可插拔的传输实现 | TransportBackend | 事件队列（内部） |
| `storage` | 控制平面持久化 | Repository 模式 | 节点、订阅、配置 |
| `runtime` | 运行时基础设施 | WaiterRegistry, EventRouter | 无 |
| `nodes` | 节点类型实现 | NodeRuntime, Session (仅智能体) | 无 |
| `daemon` | 进程管理 | ProcessMonitor, RestartManager | 无 |
| `cli` | 用户交互 | Click 命令 | 无 |
| `utils` | 通用工具 | ID 生成、序列化、路径 | 无 |

### 6.3 扩展点

- **新增节点类型**: 实现 `NodeRuntime` 接口
- **新增传输后端**: 实现 `TransportBackend` 接口
- **新增 Session 策略**: 扩展 `SessionScopeStrategy`

---

**文档结束**

_下一步: 开始实现 `core` 模块的接口定义_

