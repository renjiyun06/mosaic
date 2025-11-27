# 崩溃恢复机制

## 1. 进程监控

### 1.1 PID 监控
Daemon 进程通过 `ProcessMonitor` 组件持续监控所有托管节点 (Node Host) 的 PID。
*   **频率**: 1Hz (每秒一次)。
*   **方法**: `os.kill(pid, 0)`。如果抛出 `OSError`，视为进程消失。

### 1.2 僵尸进程处理
Daemon 需识别 `Z (Zombie)` 状态的进程，并执行 `waitpid` 进行收割，防止资源泄漏。

## 2. 自动重启

### 2.1 重启策略
每个节点可配置 `RestartPolicy`:
*   `mode`: `always` (总是重启), `on-failure` (仅非零退出码重启), `no` (不重启)。
*   `max_retries`: 最大重试次数。
*   `backoff`: 指数退避时间 (防止重启风暴)。

### 2.2 重启流程
1.  Monitor 检测到进程死亡。
2.  检查重试次数是否超限。
3.  计算退避时间并等待。
4.  Daemon 重新拉起 Node Host 进程。

## 3. 事件可靠性 (At-least-once)

### 3.1 恢复窗口 (Recovery Window)
为了防止节点在处理事件时崩溃导致事件丢失（处于 `processing` 状态但永远无法完成），引入恢复窗口机制。

*   **机制**: Transport 层在拉取待处理事件时，不仅查询 `status='pending'`，还会查询 `status='processing'` 且 `updated_at < (now - window)` 的事件。
*   **默认窗口**: 5 分钟。
*   **效果**: 崩溃节点的未完成事件会在超时后自动变为可见，被重启后的节点（或竞争消费者）重新处理。

### 3.2 ACK/NACK
*   **ACK**: 节点处理成功后调用，状态变为 `completed`。
*   **NACK**: 明确拒绝或处理失败，状态回退为 `pending` (带重试计数) 或 `failed` (死信)。

## 4. 会话状态恢复

### 4.1 Backend Session
Backend Session 存在于内存中，进程崩溃即丢失。
*   **策略**: 依赖 **按需重建**。
*   **流程**: 节点重启后，当收到属于旧会话序列的新事件时，由于内存中无此会话，`SessionManager` 会根据路由规则重新创建一个新的 Backend Session。
*   **限制**: 历史上下文会丢失（除非实现了持久化存储和加载，目前 V1 版本暂不包括完整的上下文持久化）。

### 4.2 Interactive Agent
Interactive Agent 是独立进程，Daemon 重启 Node Host 后，Agent 与 Runtime 的 IPC 连接断开。
*   **策略**: **自动重连**。
*   **流程**: Agent 进程内有重连循环，检测到 Socket 断开后会尝试重新连接新的 Node Host 进程。
