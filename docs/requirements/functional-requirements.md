# 功能需求说明书

## 1. 核心功能

### 1.1 节点管理
*   **节点创建**: 支持创建不同类型的节点（CC Agent, Scheduler, Webhook 等）。
*   **节点标识**: 每个节点拥有全局唯一的 ID 和所属的 Mesh ID。
*   **节点生命周期**: 支持节点的启动、停止、重启和状态查询。
*   **节点模式**:
    *   **Interactive**: 交互模式，用户通过 CLI 直接操作。
    *   **Background**: 后台模式，无头运行，响应事件。
    *   **Program**: 编程模式，用于配置和培训节点职责。

### 1.2 网格 (Mesh) 管理
*   **Mesh 隔离**: 支持多 Mesh 实例共存，数据和通信物理隔离。
*   **初始化**: 提供 Mesh 环境初始化工具（数据库、目录结构）。
*   **重置**: 支持清理和重置 Mesh 状态。

### 1.3 事件系统
*   **事件定义**: 支持标准化的事件结构（ID, Source, Target, Type, Payload, SessionTrace）。
*   **事件发送**:
    *   **Fire-and-Forget**: 发送即走，不等待回复。
    *   **Blocking**: 阻塞发送，等待接收方回复（用于审计/授权）。
    *   **Reply**: 对特定事件进行回复。
*   **事件接收**: 基于 Inbox 模式的异步事件消费。
*   **事件持久化**: 保证 At-least-once 投递，事件数据持久化存储。

### 1.4 订阅管理
*   **订阅关系**: 支持建立源节点到目标节点的订阅。
*   **事件过滤**: 支持基于事件类型的模式匹配（支持通配符）。
*   **阻塞订阅**: 支持声明阻塞式订阅（`!EventName`），强制上游等待决策。
*   **会话策略**: 支持在订阅中配置下游的会话路由策略 (Session Strategy)。

### 1.5 会话管理 (Agent 节点)
*   **多模式支持**:
    *   **Backend Session**: 运行时内部的轻量级会话，适合高并发。
    *   **Interactive Agent**: 外部独立进程，支持用户交互。
*   **会话路由**: 根据订阅配置 (Session Strategy) 将事件路由到正确的会话。
    *   支持镜像（Mirroring）、聚合（Aggregation）、独立任务（Tasking）等策略。
    *   支持负载均衡（Round Robin, Load Balanced）。
*   **会话生命周期**: 自动创建、复用和清理会话。

### 1.6 Claude Code 集成
*   **Hook 捕获**: 捕获 Claude Code 的生命周期事件（PreToolUse, PostToolUse 等）。
*   **MCP 工具集成**:
    *   提供回复阻塞事件的工具（`respond_to_pre_tool_use`）。
    *   提供主动发送消息的工具。
*   **System Prompt 注入**: 自动根据 Mesh 拓扑和事件语义生成 System Prompt。

## 2. 命令行接口 (CLI)

*   `mosaic init`: 初始化 Mesh。
*   `mosaic create`: 创建节点。
*   `mosaic run`: 以交互模式运行节点。
*   `mosaic start`: 启动后台节点。
*   `mosaic sub`: 管理订阅关系。
*   `mosaic list/ps`: 查看系统状态。
*   `mosaic daemon`: 管理守护进程。

## 3. 守护进程 (Daemon)

*   **进程监控**: 实时监控节点进程存活状态。
*   **自动恢复**: 根据策略自动重启崩溃的节点。
*   **控制接口**: 提供管理节点进程的 API。
