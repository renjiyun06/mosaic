# Phase 2: Daemon & Process Management

## 目标
实现进程的自动化管理和故障恢复。

## 任务清单

### 1. Daemon 实现
- [ ] 实现 `ProcessManager`: 封装 `subprocess` 调用。
- [ ] 实现 `Monitor`: 定期检查 PID 和心跳时间戳。
- [ ] 实现 `ControlServer`: 响应 CLI 命令。

### 2. CLI 工具
- [ ] `mosaic start <node_id>`: 发送指令给 Daemon。
- [ ] `mosaic ps`: 查询 Daemon 获取节点状态。

### 3. 联调
- [ ] 使用 CLI 启动 Phase 1 中的 `EchoNode`。
- [ ] 手动 Kill 节点进程，验证 Daemon 能自动拉起。

## 验收标准
*   Daemon 能够接管 Phase 1 开发的节点。
*   支持显式注册模式：Daemon 根据配置执行指定的 Python 启动命令。
