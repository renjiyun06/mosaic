# Phase 1: Core Kernel 基础

## 目标
构建系统的内核与契约，实现能够独立运行、收发消息的 `BaseNode` 框架，并建立标准事件库。

## 任务清单

### 1. Core 模块 (Kernel & Contract)
- [ ] 实现 `MeshEvent` 等基础模型。
- [ ] **核心任务**: 建立 `StandardEvents` 库 (定义的 `PreToolUse` 等事件模型)。
- [ ] **核心任务**: 建立 `CapabilityRegistry` 静态配置 (定义 `cc-agent` 等节点类型的能力)。
- [ ] 实现 `MeshClient`，封装 Transport。
- [ ] 实现 `BaseNode`。
    - `start()` 启动流程 (包含能力自检)。
    - `_run_forever()` 事件循环。
    - `_heartbeat()` 心跳维持。

### 2. Transport 插件
- [ ] 实现 `SQLiteTransportBackend`。
    - `send()`: 写入 DB + UDS Signal。
    - `receive()`: 轮询 DB。

### 3. 验证
- [ ] 编写一个简单的 `EchoNode(BaseNode)`。
- [ ] 验证 CLI 可以通过查询 Core 读取到 `EchoNode` 的能力定义。
- [ ] 运行 `EchoNode`，验证其能启动并连接 DB。

## 验收标准
*   Core 模块包含清晰的事件定义和节点能力表。
*   可以不依赖 Daemon，直接通过 Python 脚本启动一个节点进程。
