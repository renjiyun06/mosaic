# Daemon 模块

## 职责
作为守护进程，负责管理 Mosaic Mesh 中所有 Node Host 进程的生命周期。

## 关键组件

### ProcessManager
负责底层的 OS 进程操作。
*   `spawn`: 启动节点宿主进程 (Node Host)，配置环境变量，重定向日志。
*   `kill`: 发送信号终止进程。

### ProcessMonitor
负责监控循环。
*   定期检查 PID 存活。
*   维护内存中的节点状态表 (`NodeRegistry`)。

### RestartManager
实现故障恢复策略。
*   根据 `RestartPolicy` 决定是否重启。
*   计算指数退避时间。

### ControlServer
提供 UDS 接口 (`~/.mosaic/<mesh_id>/daemon.sock`)，响应 CLI 的管理命令 (start, stop, restart, status)。
