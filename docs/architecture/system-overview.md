# 系统架构概览

## 1. 总体架构

Mosaic 采用 **Core-Kernel (内核驱动)** 架构。系统由**内核 (Core)**、**守护进程 (Daemon)**、**传输插件 (Transport)** 和 **业务节点 (Nodes)** 组成。

### 核心理念：Core 即运行时
不再区分“抽象层”和“运行时层”。`mosaic.core` 模块就是系统的运行时，它提供了驱动节点运行所需的一切基础设施。

```mermaid
graph TD
    User[用户/CLI] --> Daemon[Daemon 守护进程]
    
    subgraph "Node Process (Worker)"
        direction TB
        Entry[Entrypoint] --> Kernel[Core: BaseNode]
        
        subgraph "Core Kernel"
            Loop[Event Loop]
            Client[Mesh Client]
            Heart[Heartbeat]
        end
        
        Kernel --驱动--> Logic[User Logic (e.g. CC Agent)]
        Kernel --使用--> Transport[SQLite Transport]
    end
    
    Transport <--> DB[(events.db)]
    Daemon -.监控.-> Entry
```

## 2. 核心组件

### 2.1 节点内核 (Core Kernel)
*   **实体**: `mosaic.core.BaseNode`
*   **职责**: 
    *   **生命周期管理**: 启动初始化、优雅退出。
    *   **系统协议**: 自动维持与 Daemon 的心跳，无需业务代码干预。
    *   **事件驱动**: 运行主事件循环，从 Transport 拉取消息并回调业务逻辑。
    *   **资源管理**: 管理数据库连接和 Socket 句柄。

### 2.2 业务节点 (User Nodes)
*   **实体**: `mosaic.nodes.*` (继承自 `BaseNode`)
*   **职责**: 纯粹的业务逻辑。
    *   **消费**: 实现 `process_event()` 处理业务。
    *   **生产**: 调用 `self.send()` 发送事件。
    *   **声明**: 声明自身的能力（产生的事件类型、需要的配置）。

### 2.3 守护进程 (Daemon)
*   **职责**: **运维操作员**。
*   **边界**: 它不关心节点内部如何运行，只关心进程是否存活 (PID/Heartbeat)。
*   **能力**: 
    *   通过命令行启动节点进程。
    *   监控节点健康状态。
    *   执行重启策略。

### 2.4 传输层 (Transport Layer)
*   **职责**: **哑管道 (Dumb Pipe)**。
*   **功能**: 仅负责将比特流写入磁盘 (SQLite) 或通过 Socket 发送信号。不包含任何业务逻辑。

## 3. 运行机制

### 3.1 启动流程 (显式注册模式)
1.  **Daemon** 根据配置，执行启动命令: `python -m my_project.main`。
2.  **User Code** 在 `main.py` 中实例化自己的节点类 `MyNode()`。
3.  用户调用 `MyNode.start()`。
4.  **Core Kernel** 接管控制权：
    *   初始化 `MeshClient`。
    *   连接 `Transport`。
    *   启动后台心跳线程。
    *   进入 `while True` 循环，开始消费事件。

### 3.2 事件流转
1.  **接收**: Kernel 的 `_run_forever` 循环从 Transport 拉取 `Envelope`。
2.  **分发**: Kernel 调用用户实现的 `process_event(event)`。
3.  **处理**: 用户代码执行业务逻辑。
4.  **确认**: Kernel 自动（或根据用户返回值）调用 `ack()`。

### 3.3 异常隔离
*   **业务异常**: 用户代码抛出异常，Kernel 捕获并记录日志，甚至可以发送报警事件，但**不会导致进程崩溃**。
*   **系统异常**: Transport 连接断开等致命错误，Kernel 尝试重连或安全退出，触发 Daemon 的重启机制。
