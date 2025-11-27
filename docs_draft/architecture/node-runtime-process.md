# Node Runtime Process 架构规范

> **文档用途**: 定义 Node Runtime Process 的抽象边界、职责与接口规范  
> **适用范围**: 所有接入 Mosaic Mesh 事件系统的节点类型实现

---

## 1. 核心定义

**Node Runtime Process (节点运行时进程)** 是 Mosaic 事件系统中节点的**唯一物理实体**与**通信门户**。

它是事件系统的“接口进程”。无论节点内部采用何种复杂的架构（如管理多个智能体进程、连接外部服务或运行定时任务），在事件系统看来，**一个节点等价于一个 Node Runtime Process**。

### 1.1 角色定位

1.  **通信门户 (Gateway)**: 它是节点接入 Mesh 网络的唯一合法端点。所有进出节点的事件（无论是 Hook 触发、消息回复还是主动发送）都必须经由该进程的 `MeshClient` 接口进行传输。
2.  **资源容器 (Container)**: 它是节点业务逻辑运行的沙箱。它持有节点运行所需的上下文（如数据库连接、会话状态、IPC 句柄）。
3.  **管理单元 (Managed Unit)**: 它是 Daemon 进程管理的最小原子单位。Daemon 通过监控该进程的生命周期（启动、停止、重启）来保障节点的可用性。

### 1.2 与 Daemon 的关系

*   **启动与父子关系**: 物理上，Daemon 通常是 Node Runtime Process 的父进程（Parent Process），负责初始化环境并拉起进程。
*   **生命周期解耦**: 尽管存在父子关系，但应采用**解耦模式 (Detached Mode)**。Daemon 的异常崩溃或重启**不应**导致 Node Runtime Process 退出。当 Daemon 重启后，它应当通过 PID 文件重新扫描并“认领”这些正在运行的进程，恢复监控状态。

---

## 2. 抽象职责

为了满足上述定位，Node Runtime Process 必须履行以下三类契约：

### 2.1 生命周期契约 (Lifecycle Contract)
进程必须具备标准的启动、运行和优雅退出机制，以便被 Daemon 自动化管理。
*   **Bootstrap**: 进程启动时的资源初始化（如连接控制平面数据库、绑定 IPC Socket）。
*   **Main Loop**: 阻塞的主运行循环，维持进程存活。
*   **Graceful Shutdown**: 响应 `SIGTERM` 信号，完成当前正在处理的事件、关闭会话、释放资源后退出。

### 2.2 运维监控契约 (Observability Contract)
进程必须具备可观测性，以便 Daemon 判断其健康状态。
*   **Heartbeat**: 定期更新心跳（如更新 PID 文件时间戳或发送 IPC 信号），证明进程未死锁。
*   **Status Reporting**: 暴露当前业务状态（如 Idle, Busy, Error），供控制平面查询。

### 2.3 业务处理契约 (Business Contract)
进程必须实现具体的业务逻辑以响应事件流。
*   **Event Consumption**: 从 `MeshInbox` 读取事件，并执行**特定于该节点类型**的消费逻辑（例如：CC 节点将事件路由给会话，Webhook 节点将事件转换为 HTTP 回调）。这是通过实现 `process_event` 抽象方法来完成的。
*   **Event Production**: 通过 `MeshOutbox` 产生事件（如定时任务触发、Web 请求转换）。

---

## 3. 接口定义 (Interface Specification)

基于上述职责，`NodeRuntime` 应设计为一个抽象基类（Abstract Base Class），封装通用的生命周期与监控逻辑，并强制子类实现业务逻辑。

```python
from abc import ABC, abstractmethod
from typing import Optional
import asyncio

class NodeRuntime(ABC):
    """
    Node Runtime Process 的核心抽象基类。
    所有节点类型（CC, Scheduler, Webhook）均需继承此类。
    """

    def __init__(self, client: MeshClient):
        self.client = client
        self._running = False
        self._shutdown_event = asyncio.Event()

    # =========================================================================
    # 1. 生命周期管理 (Template Method 模式)
    # =========================================================================

    async def run(self) -> None:
        """
        进程主入口 (由启动脚本调用)。
        负责编排整个生命周期：初始化 -> 注册信号 -> 启动心跳 -> 运行业务 -> 清理。
        """
        try:
            # 1. 资源初始化
            await self.client.connect()
            await self.bootstrap()
            self._running = True

            # 2. 启动辅助任务 (心跳)
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # 3. 进入业务主循环 (阻塞直到退出信号)
            # 使用 wait_for_shutdown 允许业务循环被信号打断
            await self.loop()

        except Exception as e:
            # 记录致命错误
            self._log_error(e)
            raise
        finally:
            # 4. 优雅退出
            self._running = False
            if heartbeat_task:
                heartbeat_task.cancel()
            await self.shutdown()
            await self.client.disconnect()

    async def stop(self) -> None:
        """触发停止信号 (通常由信号处理器调用)"""
        self._shutdown_event.set()

    # =========================================================================
    # 2. 必须实现的业务接口 (Abstract Methods)
    # =========================================================================

    @abstractmethod
    async def bootstrap(self) -> None:
        """
        业务资源初始化钩子。
        子类应在此处建立 DB 连接、加载模型或启动内部服务器。
        """
        pass

    @abstractmethod
    async def loop(self) -> None:
        """
        业务主循环。
        
        默认行为可以是监听 Inbox:
            while self._running:
                async for envelope in self.client.inbox:
                    await self.process_event(envelope)
        
        Scheduler 节点可覆盖此方法以执行定时逻辑。
        """
        pass

    @abstractmethod
    async def process_event(self, envelope: EventEnvelope) -> None:
        """
        事件处理逻辑。
        
        当 loop() 采用默认的消费者模式时，此方法被调用。
        子类在此处实现具体的事件路由、处理或分发。
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        业务资源清理钩子。
        子类应在此处关闭会话、断开外部连接。
        """
        pass

    # =========================================================================
    # 3. 运维监控实现 (Base Implementation)
    # =========================================================================

    async def _heartbeat_loop(self) -> None:
        """
        内部心跳循环。
        定期更新进程活跃状态，供 Daemon 监控。
        """
        while self._running:
            # 示例: touch ~/.mosaic/<mesh>/pids/<node>.pid
            # 或发送 IPC 信号
            await self._send_heartbeat()
            await asyncio.sleep(1)  # 1秒心跳

    async def _send_heartbeat(self) -> None:
        """具体的心跳发送逻辑 (可由 mixin 提供)"""
        pass
```

### 3.1 典型实现示例

#### 场景 A: 智能体节点 (CC Node)
*   **bootstrap**: 初始化 `SessionManager`，启动 MCP Server。
*   **loop**: 使用默认消费者循环。
*   **process_event**: 解析事件中的 `session_trace`，调用 `SessionManager` 获取对应会话，将事件投递给智能体。
*   **shutdown**: 通知所有活跃会话保存状态并退出。

#### 场景 B: 调度器节点 (Scheduler Node)
*   **bootstrap**: 加载定时任务配置。
*   **loop**: 
    *   覆盖默认循环。
    *   运行 `while self._running:` 循环，检查时间并调用 `self.client.outbox.send()` 产生事件。
*   **process_event**: 空实现（不消费事件）。
*   **shutdown**: 保存任务执行进度。

