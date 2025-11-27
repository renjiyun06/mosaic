# Mosaic Event System Specification (Abstract Layer)

> **Status**: Draft
> **Date**: 2025-11-23
> **Version**: 1.4
> **Context**: Core Abstraction Definition

## 1. 引言 (Introduction)

**Mosaic** 是一个通用的、分布式的事件驱动网格 (Mesh) 基础设施。它的核心愿景是将异构的智能体（Agents）和系统组件（Components）像马赛克一样灵活拼接，构建出能够解决复杂问题的协作网络。

本文档仅定义 Mosaic 事件系统的**抽象接口层 (Abstraction Layer)**。它规定了组件节点如何与 Mesh 网络交互的契约，而不涉及底层的具体实现技术（如存储引擎或通信协议）。

### 1.1 设计原则

*   **组件自治 (Autonomy)**: 每个节点都是独立的计算单元，通过标准接口与外部通信。
*   **语义中立 (Semantic Neutrality)**: 事件系统只提供客观的拓扑和协议信息，不定义节点的业务角色（这是 Programming 阶段的职责）。
*   **LLM-Native**: 接口设计考虑到智能体的特性，提供丰富的语义元数据以构建上下文。

---

## 2. 概念模型 (Conceptual Model)

### 2.1 The Mesh (网格网络)

**Mesh** 是一个逻辑隔离的事件状态空间。
*   它定义了节点通信的边界。处于不同 Mesh 中的节点在物理上和逻辑上都是完全隔离的。
*   它承载了网络拓扑（Topology），即节点之间的订阅关系。

### 2.2 The Node (组件节点)

**Node** 是 Mesh 网络中的基本活动单元。
*   **独立性**: 对应一个独立的 OS 进程或执行上下文。
*   **标识**: 拥有唯一的 `node_id`。

### 2.3 Event Semantics (事件语义)

为了让智能体理解它们处理的数据，事件必须包含**自描述的语义信息**。
*   **Event Type**: 唯一标识符 (e.g. `PreToolUse`)。
*   **Event Schema**: 数据结构定义 (JSON Schema)。
*   **Event Description**: 自然语言描述，用于注入智能体的 System Prompt。

---

## 3. 接口规范 (Interface Specification)

Mosaic 将接口划分为三个平面：**数据平面** (I/O), **控制平面** (Management), 和 **上下文平面** (Context)。

### 3.1 数据平面：MeshClient (Data Plane)

`MeshClient` 是节点进程持有的上下文对象，代表了与 Mesh 网络的运行时会话。

```python
class MeshClient(ABC):
    """
    组件节点接入 Mosaic 网络的唯一运行时入口。
    """
    @property
    def node_id(self) -> str: ...

    @property
    def mesh_id(self) -> str: ...
    
    @property
    def inbox(self) -> 'MeshInbox':
        """获取事件输入通道"""
        ...
    
    @property
    def outbox(self) -> 'MeshOutbox':
        """获取事件输出通道"""
        ...
    
    @property
    def context(self) -> 'MeshContext':
        """获取上下文查询接口"""
        ...
```

#### 3.1.1 输入通道：MeshInbox (Input Channel)

**MeshInbox** 抽象了节点对事件的消费能力。它采用 **异步迭代器 (Async Iterator)** 模式。

```python
class MeshInbox(ABC):
    @abstractmethod
    def __aiter__(self) -> AsyncIterator['EventEnvelope']:
        """
        返回一个异步迭代器，源源不断地产生事件信封。
        当没有新事件时，迭代器会挂起等待 (Await)，直到有新事件到达。
        """
        pass

class EventEnvelope(ABC):
    """
    封装了事件数据与交付状态控制。
    """
    @property
    def event(self) -> MeshEvent:
        """获取实际的事件数据对象"""
        pass

    @abstractmethod
    async def ack(self) -> None:
        """确认消费 (Commit)。实现 At-least-once 语义。"""
        pass

    @abstractmethod
    async def nack(self, reason: str = None) -> None:
        """拒绝消费 (Rollback)。触发重试或死信策略。"""
        pass
```

#### 3.1.2 输出通道：MeshOutbox (Output Channel)

**MeshOutbox** 抽象了节点产生事件的能力。

```python
class MeshOutbox(ABC):
    @abstractmethod
    async def send(self, event: MeshEvent) -> None:
        """
        [发送事件]
        将一个事件发布到 Mesh 网络中。
        语义: Fire-and-Persistence (发送即持久化)
        """
        pass

    @abstractmethod
    async def reply(self, target_event_id: str, payload: Any) -> None:
        """[回复事件] 便捷方法，用于构建 Request-Response 模式。"""
        pass
```

### 3.2 控制平面：MeshAdmin (Control Plane)

用于网络配置和元数据注册。此接口主要由 CLI 或节点初始化代码使用。

```python
class MeshAdmin(ABC):
    @abstractmethod
    async def register_node_capabilities(
        self, 
        node_type: str, 
        produced_events: List[EventTypeDefinition],
        consumed_events: List[EventTypeDefinition]
    ) -> None:
        """
        [注册能力]
        声明某种类型的节点：
        1. 会产生哪些事件 (Produced Events)
        2. 能处理哪些事件 (Consumed Events)
        这建立了事件类型的语义库和节点的能力图谱。
        """
        pass

    @abstractmethod
    async def subscribe(self, subscriber_id: str, publisher_id: str, event_pattern: str) -> None:
        """建立订阅关系"""
        pass
        
    # ... create_node, unsubscribe ...
```

### 3.3 上下文平面：MeshContext (Context Plane)

这是 **LLM-Native** 设计的核心。它允许节点查询其在网络中的"客观处境"，以便 Runtime 将其注入到 System Prompt 中。

```python
class MeshContext(ABC):
    """
    提供节点在网络中的客观环境信息。
    """
    @abstractmethod
    async def get_topology_context(self) -> TopologyContext:
        """
        获取拓扑视图：
        1. Upstream: 谁订阅了我？(影响我的输出决策)
        2. Downstream: 我订阅了谁？(影响我的输入预期)
        """
        pass

    @abstractmethod
    async def get_event_semantics(self, event_types: List[str]) -> Dict[str, EventTypeDefinition]:
        """
        获取事件的语义描述。
        用于告诉智能体："你收到的 'PreToolUse' 事件意味着..."
        """
        pass

@dataclass
class EventTypeDefinition:
    name: str
    description: str  # 给 AI 看的语义说明
    schema: Dict      # JSON Schema
```

---

## 4. 交互语义 (Interaction Semantics)

### 4.1 启动引导 (Bootstrapping)

当一个智能体节点启动时，Runtime 应执行以下引导流程：

1.  **Connect**: 连接到 Mesh。
2.  **Introspect (自省)**: 调用 `client.context.get_topology_context()` 获取自身位置。
3.  **Enrich (增强)**: 调用 `client.context.get_event_semantics()` 获取相关事件的自然语言描述。
4.  **Prompt Construction**: 将上述信息（拓扑事实 + 事件语义）注入 System Prompt。
5.  **Loop**: 开始 Inbox 消费循环。

**注意**: 此时 System Prompt 中仅包含客观事实。具体的"角色 (Role)"和"行为准则"应由 Programming 阶段的用户指令补充。

### 4.2 事件路由与可靠性

Mosaic 采用 **发送端分发 (Sender-side Dispatch)** 策略：路由和分发在 `Outbox.send()` 阶段通过查询数据库完成。系统保证 **At-least-once** 投递语义，并确保不同 Mesh 网络之间的物理隔离。
