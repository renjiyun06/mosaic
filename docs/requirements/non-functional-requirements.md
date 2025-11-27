# 非功能需求说明书

## 1. 可靠性 (Reliability)

*   **At-least-once Delivery**: 事件投递必须保证至少送达一次。系统需具备 ACK/NACK 机制和超时重传能力。
*   **Crash Recovery**:
    *   Daemon 进程应由系统级管理器（如 systemd）守护。
    *   Node 进程崩溃后应能由 Daemon 自动拉起。
    *   事件处理需具备幂等性，以应对重复投递。
    *   支持恢复窗口机制，超时未完成的事件应重新可见。
*   **阻塞超时**: 阻塞调用必须有超时机制，防止死锁。

## 2. 性能 (Performance)

*   **低延迟**: 本地 IPC（Unix Domain Socket）通信延迟应在毫秒级。
*   **并发处理**: Node Runtime 应能高效处理并发事件，不阻塞主循环。
*   **资源占用**: Backend Session 应保持轻量，避免不必要的进程开销。

## 3. 可扩展性 (Extensibility)

*   **可扩展架构**: 节点类型（Node Type）应易于扩展，支持接入 Gemini, LangChain 等其他 Agent 框架。
*   **传输层可插拔**: 支持替换底层传输实现（从 SQLite 切换到 Kafka/Redis），而不影响业务逻辑。
*   **事件类型扩展**: 支持动态注册新的事件类型。

## 4. 可维护性 (Maintainability)

*   **清晰的模块边界**: Core, Runtime, Transport, Storage 等模块职责单一，依赖关系清晰。
*   **日志与监控**: 提供详细的运行日志和状态指标，便于排查问题。
*   **代码规范**: 代码需符合 Python 类型提示规范，并通过静态检查。

## 5. 安全性 (Security)

*   **隔离性**: 不同 Mesh 实例之间的数据和通信必须严格隔离。
*   **权限控制**: 阻塞订阅机制应能可靠地拦截敏感操作（如 PreToolUse）。
*   **输入校验**: 对所有进出系统的事件数据进行 Schema 校验。
