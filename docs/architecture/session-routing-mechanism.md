# 智能体节点会话路由机制

## 1. 核心概念

**会话路由 (Session Routing)** 是智能体节点（Agent Node）处理入站事件时的首要计算过程。

由于智能体节点通常维护着多个并发的会话实例（Session），当一个事件到达时，节点必须计算出：**该事件应该由哪个会话来处理？**

从本质上讲，这是一个纯函数计算：

$$ \text{TargetSessionID} = f(\text{Event}, \text{Strategy}) $$

*   **Event**: 包含上游上下文信息的事件数据。
*   **Strategy**: 下游节点预先配置的路由策略。

## 2. 数据契约

为了支持路由计算，事件系统的数据平面（Data Plane）必须在传递事件时携带必要的上下文信息。这是 Core 层对路由机制的唯一支持。

### MeshEvent 的必要字段

`MeshEvent` 必须包含 `session_trace` 字段，作为路由函数的关键入参。

```python
class SessionTrace:
    """
    事件中的上游上下文元数据。
    用于下游节点计算路由目标，不决定下游的具体行为。
    """
    upstream_session_id: str  # 产生事件时的会话 ID
    event_seq: int            # 会话内的事件序号 (用于乱序重排与去重)
```

### 路由函数的签名

在节点实现层（`nodes/`），路由逻辑遵循以下统一签名：

```python
def route_event(event: MeshEvent, config: dict) -> str:
    """
    输入：事件对象，订阅配置
    输出：目标 Session ID
    """
```

## 3. 标准路由策略

基于智能体协作的典型模式，系统提供以下标准路由函数。每种策略都可以通过 CLI 参数进行微调。

### 3.1 镜像模式 (Mirroring)

*   **语义**：下游节点作为上游节点的“影子”或“副驾驶”。
*   **逻辑**：为上游的每一个会话，在下游维护一个对应的会话。
*   **计算公式**：
    ```python
    # 伪代码示例
    # 默认合并：来自同一上游会话的所有事件，进入同一个下游会话
    # Topic隔离：不同 Topic 的事件，进入不同的下游会话
    # 必须包含 mesh_id 以确保全局唯一性
    target_session_id = hash(event.mesh_id, event.source_id, event.session_trace.upstream_session_id, config.topic)
    ```
*   **典型参数**：
    *   `topic` (string, optional): 隔离命名空间。用于将同一上游的不同事件流分流到不同会话。
    *   `buffer_size` / `buffer_timeout`: 缓冲参数（通常较少用于镜像模式，但在高频审计场景可用）。
*   **使用示例**：
    ```bash
    # 场景：审计节点需要“跟随”Worker的每个操作，保持完整的上下文连贯性。
    mosaic sub auditor worker "!PreToolUse" --session-routing-strategy mirroring

    # 场景：同一 Auditor 针对不同类型的敏感操作，建立隔离的镜像审计会话。
    # 1. 文件操作 -> 路由到 "file_audit" 会话（从文件加载 Prompt）
    mosaic sub auditor worker "FileWrite,FileDelete" \
        --session-routing-strategy mirroring \
        --param topic=file_audit \
        --param prompt_file="prompts/file_auditor.md"
    
    # 2. 网络操作 -> 路由到 "net_audit" 会话（从文件加载 Prompt）
    mosaic sub auditor worker "Http,Curl" \
        --session-routing-strategy mirroring \
        --param topic=net_audit \
        --param prompt_file="prompts/net_auditor.md"
    ```

### 3.2 任务模式 (Tasking)

*   **语义**：一事一议，处理完即销毁。
*   **逻辑**：每个事件被视为一个独立的任务，启动全新的会话进行处理。
*   **计算公式**：
    ```python
    # 一一对应：为每个EventID生成一个唯一的TargetSessionID
    # 具体实现通常使用 UUID 或 Hash(EventID)
    # EventID 本身是全局唯一的 UUID，因此不需要额外的 Seed
    target_session_id = generate_unique_id(seed=event.event_id)
    ```
*   **典型参数**：
    *   `prompt` (string): 会话启动时的系统提示词文本。
    *   `prompt_file` (string): 提示词文件路径。如果是相对路径，则相对于节点 workspace 查找。
    *   `buffer_size` (int): 缓冲事件数量。凑够 N 个事件后合并为一个批次发送，节省 Token。
    *   `buffer_timeout` (int): 缓冲最大等待时间（秒）。
*   **使用示例**：
    ```bash
    # 场景：代码分析节点，对每次 Git 提交（事件）进行独立分析，互不干扰。
    mosaic sub analyzer git_watcher "PushEvent" --session-routing-strategy tasking

    # 场景：批量分析报警。从文件中加载严格的分析规则。
    mosaic sub analyzer monitor "Alert" \
        --session-routing-strategy tasking \
        --param buffer_size=10 \
        --param buffer_timeout=60 \
        --param prompt_file="prompts/strict_analysis.md"
    ```

### 3.3 聚合模式 (Aggregation)

*   **语义**：多源汇聚，全局统一处理。
*   **逻辑**：忽略上游的会话边界，将所有来源的事件路由到同一个指定的长期会话。
*   **计算公式**：
    ```python
    # 如果指定了 name，则为命名会话；否则为默认全局会话
    # 全局会话在 Mesh 内唯一
    target_session_id = f"{event.mesh_id}:global:{config.name}" if config.name else f"{event.mesh_id}:global_primary"
    ```
*   **典型参数**：
    *   `name` (string): 聚合会话的名称。
    *   `buffer_size` (int): 凑够 N 个事件再投递给会话。
    *   `buffer_timeout` (int): 最多等待 T 秒。
*   **使用示例**：
    ```bash
    # 场景：中央日志节点，将所有 Worker 的日志汇总到一个主会话中进行摘要。
    # 关键优化：每 20 条日志打包处理一次，避免频繁 LLM 调用消耗 Token。
    mosaic sub logger worker "*" \
        --session-routing-strategy aggregation \
        --param buffer_size=20 \
        --param buffer_timeout=300

    # 场景：运维中心，专门用一个 "incident_room" 会话来处理所有节点的报警事件。
    mosaic sub ops_center "*" "Alert" \
        --session-routing-strategy aggregation \
        --param name=incident_room
    ```

### 3.4 闭环模式 (Reply Loop)

*   **语义**：请求与响应的闭环。
*   **逻辑**：如果收到的是对之前请求的回复（Reply），必须将其路由回发出请求的那个会话。
*   **计算公式**：
    ```python
    # 需要节点内部维护 EventID -> SessionID 的映射表
    target_session_id = lookup_context(event.reply_to)
    ```
*   **典型参数**：无（完全依赖 `event.reply_to` 字段）。
*   **使用示例**：
    ```bash
    # 场景：Worker 接收之前发出的工具调用请求的审批结果。
    # 通常由系统自动处理，但在显式订阅时：
    mosaic sub worker auditor "NodeMessage" --session-routing-strategy reply_loop
    ```

### 3.5 有状态模式 (Stateful / Lifecycle)

*   **语义**：事件驱动的会话生命周期管理。
*   **逻辑**：上游或事件本身控制会话的开启与关闭，中间的事件基于上下文ID路由到该动态会话。
*   **核心参数**：
    *   `context_key` (string): **[必填]** 事件 Payload 中用于关联的业务键（如 `task_id`）。
    *   `start_on` (pattern): 触发创建新会话的事件模式。
    *   `end_on` (pattern): 触发关闭会话的事件模式。
*   **计算公式**：
    ```python
    key = event.payload.get(config.context_key)
    if event matches config.start_on:
        create_session(key)
    target_session_id = lookup_session(key)
    if event matches config.end_on:
        defer_close_session(target_session_id)
    ```
*   **使用示例**：
    ```bash
    # 场景：Controller 动态控制 Worker 开启一个会话来处理特定的 Task。
    # 1. 收到 TaskStart (含 task_id=101) -> 开启会话
    # 2. 收到 Log (含 task_id=101) -> 路由到该会话
    # 3. 收到 TaskEnd (含 task_id=101) -> 关闭会话
    mosaic sub worker controller "*" \
        --session-routing-strategy stateful \
        --param context_key=task_id \
        --param start_on="TaskStart" \
        --param end_on="TaskEnd"
    ```

## 4. 架构边界

此设计明确了系统模块的职责边界：

1.  **Core (Mosaic Core)**：
    *   **不感知**路由逻辑。
    *   **只负责**传递 `session_trace` 数据。
    *   `Subscription` 模型中只存储策略名称字符串（如 `"mirroring"`），不包含具体逻辑。

2.  **Nodes (Agent Implementation)**：
    *   **负责**实现具体的路由函数。
    *   **负责**维护会话生命周期（根据计算出的 TargetSessionID 创建或复用会话）。

## 5. 模块归属

为了支持智能体节点的代码复用，`nodes` 模块将采用分层结构。会话路由逻辑归属于 **智能体通用层**。

### 目录结构规划

```text
src/mosaic/nodes/
├── agent/                   # 智能体节点专用目录
│   ├── routing/             # [核心] 会话路由策略代码
│   │   ├── __init__.py
│   │   ├── strategy.py      # 策略接口定义 (RoutingStrategy)
│   │   ├── registry.py      # 策略注册表
│   │   └── strategies/      # 具体策略实现
│   │       ├── __init__.py
│   │       ├── mirroring.py    # MirroringStrategy
│   │       ├── tasking.py      # TaskingStrategy
│   │       ├── aggregation.py  # AggregationStrategy
│   │       ├── reply_loop.py   # ReplyLoopStrategy
│   │       └── stateful.py     # StatefulStrategy
│   │
│   ├── base.py              # AgentNodeRuntime 基类 (集成路由逻辑)
│   │
│   ├── cc/                  # Claude Code 实现 (继承 AgentNodeRuntime)
│   └── gemini/              # Gemini 实现 (继承 AgentNodeRuntime)
│
├── scheduler/               # 非智能体节点 (无需路由逻辑)
└── webhook/                 # 非智能体节点 (无需路由逻辑)
```

### 策略接口定义 (Pseudo-code)

```python
# src/mosaic/nodes/agent/routing/strategy.py

from abc import ABC, abstractmethod
from typing import Any, Dict
from mosaic.core.models import MeshEvent

class RoutingStrategy(ABC):
    """
    Abstract base class for all session routing strategies.
    """

    @abstractmethod
    def route(self, event: MeshEvent, params: Dict[str, Any]) -> str:
        """
        Calculate the target session ID based on the event context and parameters.

        Args:
            event: The incoming event containing session_trace.
            params: User-provided parameters from the subscription (e.g., topic, concurrency).

        Returns:
            Target Session ID string.
        """
        pass

    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        Optional: Validate if the provided parameters are valid for this strategy.
        Raises ValueError if invalid.
        """
        pass
```

### 职责划分

*   **`nodes.agent.routing`**: 包含所有标准路由策略的纯函数实现。这是路由逻辑的**物理归属**。
*   **`nodes.agent.base.AgentNodeRuntime`**: 智能体节点的基类，负责在运行时加载路由策略，并调用计算目标会话 ID。
*   **`nodes.agent.cc.CCNodeRuntime`**: 具体实现类，只需要配置默认策略或覆盖特殊行为，无需重复实现通用的路由算法。

这种设计确保了路由逻辑在所有智能体类型（Claude, Gemini, Cursor）之间的高度复用，同时保持了与非智能体节点的清晰隔离。
