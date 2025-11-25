# Mosaic 崩溃恢复设计

> **文档用途**: 定义节点进程崩溃后的恢复机制  
> **创建日期**: 2025-11-24  
> **前置文档**: `event-system-spec.md`, `concepts-glossary.md`

---

## 1. 概述

本文档描述 Mosaic 系统中节点进程崩溃后的恢复机制，包括：
1. **进程监控与重启**：Daemon 如何检测和重启崩溃的节点进程
2. **事件投递保证**：如何确保事件不丢失（At-least-once 语义）
3. **会话恢复**：崩溃后会话状态的重建

---

## 2. 崩溃场景分析

### 2.1 进程层级

```
Mosaic Daemon Process
    ↓ 管理
Node Runtime Process
    ↓ 管理（IPC 协作）
Agent Process (Interactive)
```

### 2.2 可能的崩溃点

| 崩溃点 | 影响范围 | 恢复策略 |
|-------|---------|---------|
| **Daemon Process** | 整个 Mesh 的进程管理失效 | 依赖系统级进程管理器（systemd） |
| **Node Runtime Process** | 该节点无法收发事件 | Daemon 自动重启 |
| **Agent Process (Backend)** | 单个后台会话失效 | Node Runtime 重建会话 |
| **Agent Process (Interactive)** | 用户会话中断 | 用户重新连接或放弃 |

---

## 3. Daemon 进程的可靠性

### 3.1 Daemon 自身的保护

Daemon 作为关键基础设施，需要外部保护机制。

#### 方案：systemd 服务管理（推荐）

```ini
# /etc/systemd/system/mosaic-daemon@.service

[Unit]
Description=Mosaic Daemon for mesh %i
After=network.target

[Service]
Type=simple
User=mosaic
WorkingDirectory=/home/mosaic

# 启动命令
ExecStart=/usr/local/bin/mosaic daemon start --mesh-id %i

# 自动重启策略
Restart=always
RestartSec=5

# 资源限制
LimitNOFILE=65536
MemoryMax=2G

[Install]
WantedBy=multi-user.target
```

**使用方式**：
```bash
# 启动 Daemon（mesh-1）
sudo systemctl start mosaic-daemon@mesh-1
sudo systemctl enable mosaic-daemon@mesh-1  # 开机自启

# 查看状态
sudo systemctl status mosaic-daemon@mesh-1

# 查看日志
sudo journalctl -u mosaic-daemon@mesh-1 -f
```

#### 方案：开发环境自动恢复

```python
# 节点进程启动时检查 Daemon
def ensure_daemon_running(mesh_id: str):
    """确保 Daemon 在线，否则自动启动"""
    pid_file = Path(f"~/.mosaic/{mesh_id}/daemon.pid").expanduser()
    
    if pid_file.exists():
        pid = int(pid_file.read_text())
        if is_process_alive(pid):
            return  # Daemon 在运行
    
    # Daemon 未运行，自动启动
    subprocess.Popen([
        "mosaic", "daemon", "start", 
        "--mesh-id", mesh_id,
        "--background"
    ])
    
    # 等待 Daemon 启动
    time.sleep(2)
```

### 3.2 Daemon 的优雅退出

```python
class MosaicDaemon:
    async def shutdown(self):
        """优雅退出"""
        logger.info("Daemon shutting down...")
        
        # 1. 停止接收新请求
        await self.control_server.stop()
        
        # 2. 通知所有 Node Runtime 准备退出
        for node_id in self.node_registry.keys():
            await self.notify_node_shutdown(node_id)
        
        # 3. 等待节点优雅退出（超时 30 秒）
        try:
            await asyncio.wait_for(
                self.wait_all_nodes_exit(),
                timeout=30
            )
        except asyncio.TimeoutError:
            logger.warning("Some nodes did not exit gracefully")
        
        # 4. 强制终止未退出的节点
        for node_id, info in self.node_registry.items():
            if info['status'] == 'running':
                logger.warning(f"Force killing node {node_id}")
                os.kill(info['pid'], signal.SIGKILL)
        
        # 5. 清理资源
        os.remove(self.pid_file)
        logger.info("Daemon stopped")
```

---

## 4. Node Runtime Process 的监控与重启

### 4.1 监控机制

#### 主监控方式：PID 检测

```python
class ProcessMonitor:
    """监控节点进程的存活状态"""
    
    async def monitor_loop(self):
        """主监控循环"""
        while self.running:
            for node_id, info in self.registry.items():
                if info['status'] == 'running':
                    # 检查进程是否存活
                    if not self.is_process_alive(info['pid']):
                        await self.on_process_died(node_id, info)
            
            await asyncio.sleep(1)  # 每秒检查一次
    
    def is_process_alive(self, pid: int) -> bool:
        """检查进程是否存活"""
        try:
            # 发送信号 0，不杀死进程，只检查是否存在
            os.kill(pid, 0)
            return True
        except OSError:
            return False
```

#### 辅助监控：心跳机制（可选）

```python
class HeartbeatMonitor:
    """基于心跳的监控（可选，用于检测僵尸进程）"""
    
    def __init__(self, timeout: float = 60):
        self.timeout = timeout
        self.last_heartbeat: Dict[str, datetime] = {}
    
    async def monitor_loop(self):
        while True:
            now = datetime.now()
            for node_id, last_time in self.last_heartbeat.items():
                elapsed = (now - last_time).total_seconds()
                if elapsed > self.timeout:
                    # 心跳超时，认为进程卡住
                    logger.warning(f"Node {node_id} heartbeat timeout")
                    await self.force_restart(node_id)
            
            await asyncio.sleep(10)
    
    def record_heartbeat(self, node_id: str):
        """节点发送心跳"""
        self.last_heartbeat[node_id] = datetime.now()
```

**节点侧心跳发送**：
```python
# Node Runtime 定期发送心跳
class NodeRuntime:
    async def heartbeat_loop(self):
        while True:
            try:
                await self.daemon_client.send_heartbeat()
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            
            await asyncio.sleep(30)  # 每 30 秒一次
```

### 4.2 重启策略

```python
class RestartManager:
    """管理节点重启"""
    
    async def on_process_died(self, node_id: str, info: dict):
        """处理进程死亡"""
        policy = info['restart_policy']
        
        # 1. 检查重启策略
        if policy['mode'] == 'no':
            logger.info(f"Node {node_id} died, no restart policy")
            await self.notify_admin(node_id, "node_died")
            return
        
        if policy['mode'] == 'on-failure':
            # 判断退出码
            exit_code = self.get_exit_code(info['pid'])
            if exit_code == 0:
                logger.info(f"Node {node_id} exited normally")
                return
        
        # 2. 检查重试次数
        crash_count = info.get('crash_count', 0)
        max_retries = policy.get('max_retries', 3)
        
        if crash_count >= max_retries:
            logger.error(f"Node {node_id} exceeded max retries ({max_retries})")
            info['status'] = 'failed'
            await self.notify_admin(node_id, "max_retries_exceeded")
            return
        
        # 3. 计算退避时间
        backoff = self.calculate_backoff(
            crash_count, 
            policy.get('backoff_seconds', 5)
        )
        
        logger.info(
            f"Restarting {node_id} after {backoff}s "
            f"(attempt {crash_count + 1}/{max_retries})"
        )
        
        await asyncio.sleep(backoff)
        
        # 4. 重启节点
        try:
            await self.start_node(node_id)
            info['crash_count'] = crash_count + 1
            info['last_restart'] = datetime.now()
        except Exception as e:
            logger.error(f"Failed to restart node {node_id}: {e}")
            info['status'] = 'failed'
    
    def calculate_backoff(self, crash_count: int, base: float) -> float:
        """指数退避"""
        return min(base * (2 ** crash_count), 300)  # 最多 5 分钟
```

### 4.3 重启策略配置

```python
@dataclass
class RestartPolicy:
    """重启策略配置"""
    mode: Literal["always", "on-failure", "no"]
    max_retries: int = 3
    backoff_seconds: float = 5
    backoff_strategy: Literal["linear", "exponential"] = "exponential"
```

**节点配置示例**：
```json
{
  "node_id": "worker",
  "node_type": "cc",
  "workspace": "/path/to/workspace",
  
  "restart_policy": {
    "mode": "always",
    "max_retries": 5,
    "backoff_seconds": 10,
    "backoff_strategy": "exponential"
  }
}
```

**CLI 配置**：
```bash
# 创建节点时指定
ccm create worker --path ./worker --restart always --max-retries 5

# 修改现有节点
ccm config worker set restart-policy always
ccm config worker set max-retries 5
```

---

## 5. 事件投递保证（At-least-once）

### 5.1 事件状态机

```
pending ──┐
          ├─→ processing ──┬─→ completed (ack)
          │                ├─→ failed (nack, requeue=false)
          │                └─→ retry_pending (nack, requeue=true)
          │
          └─→ expired (TTL 超时)

retry_pending ──→ pending (重新入队)
```

### 5.2 恢复窗口机制

**核心思想**：如果事件处于 `processing` 状态超过阈值（恢复窗口），认为节点已崩溃，将事件重新设为可见。

```python
# EventRepository
async def fetch_pending(
    mesh_id: str, 
    node_id: str, 
    recovery_window: int = 300
) -> Optional[EventEnvelope]:
    """
    获取待处理事件：
    1. status = 'pending'
    2. 或 status = 'processing' 但超过恢复窗口（默认 5 分钟）
    """
    query = """
        SELECT * FROM event_queue
        WHERE mesh_id = ?
          AND target_id = ?
          AND (
              status = 'pending'
              OR (
                  status = 'processing' 
                  AND updated_at < datetime('now', '-{recovery_window} seconds')
              )
          )
        ORDER BY created_at ASC
        LIMIT 1
    """.format(recovery_window=recovery_window)
    
    event_data = await db.fetch_one(query, [mesh_id, node_id])
    
    if event_data:
        # 标记为 processing
        await db.execute(
            """
            UPDATE event_queue 
            SET status = 'processing', 
                updated_at = ?,
                retry_count = retry_count + 1
            WHERE mesh_id = ?
              AND event_id = ?
            """,
            [datetime.now(), mesh_id, event_data['event_id']]
        )
        
        event = deserialize_event(event_data)
        envelope = EventEnvelope(event, event_data['event_id'])
        return envelope
    
    return None
```

### 5.3 ACK/NACK 机制

```python
class EventEnvelope:
    """事件信封，携带 ACK/NACK 方法"""
    
    def __init__(self, event: MeshEvent, event_id: str):
        self.event = event
        self.event_id = event_id
    
    async def ack(self):
        """确认事件已处理"""
        await EventRepository.update_status(self.event_id, "completed")
    
    async def nack(self, requeue: bool = True, reason: str = None):
        """拒绝事件"""
        if requeue:
            # 重新入队
            await EventRepository.update_status(
                self.event_id, 
                "retry_pending",
                error=reason
            )
        else:
            # 标记为失败，不再重试
            await EventRepository.update_status(
                self.event_id, 
                "failed",
                error=reason
            )
```

### 5.4 消费端处理

```python
class NodeRuntime:
    async def event_loop(self):
        """事件处理循环"""
        async for envelope in self.inbox:
            try:
                # 处理事件
                await self.process_event(envelope.event)
                
                # 确认事件
                await envelope.ack()
                
            except RetriableError as e:
                # 可重试错误，重新入队
                logger.warning(f"Retriable error: {e}")
                await envelope.nack(requeue=True, reason=str(e))
                
            except FatalError as e:
                # 致命错误，不再重试
                logger.error(f"Fatal error: {e}")
                await envelope.nack(requeue=False, reason=str(e))
```

### 5.5 幂等性要求

**At-least-once 语义要求消费端幂等处理**。

#### 方案 A：系统级幂等性检查（可选）

```python
# 增加 processed_events 表
CREATE TABLE processed_events (
    event_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result TEXT
);

# 处理前检查
async def is_already_processed(event_id: str, node_id: str) -> bool:
    result = await db.fetch_one(
        "SELECT 1 FROM processed_events WHERE event_id = ? AND node_id = ?",
        [event_id, node_id]
    )
    return result is not None
```

#### 方案 B：业务逻辑幂等（推荐）

```python
async def handle_event(envelope: EventEnvelope):
    event = envelope.event
    
    # 业务逻辑自行保证幂等性
    # 例如：使用事件 ID 作为去重键
    if await already_processed(event.event_id):
        await envelope.ack()
        return
    
    # 处理事件
    result = await process_event(event)
    
    # 记录处理结果
    await save_result(event.event_id, result)
    
    await envelope.ack()
```

### 5.6 恢复窗口配置

```python
# 全局配置
ccm config set recovery-window 300  # 5 分钟

# 按订阅配置
ccm sub auditor worker "!PreToolUse" --recovery-window 60  # 1 分钟
```

数据库 Schema：
```sql
ALTER TABLE subscriptions ADD COLUMN recovery_window INTEGER DEFAULT 300;
```

---

## 6. 阻塞事件的超时与重试

### 6.1 发送方视角

```python
class MeshOutbox:
    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float = 30,
        max_retries: int = 3
    ) -> List[Any]:
        """发送阻塞事件并等待回复"""
        
        for attempt in range(max_retries):
            try:
                # 注册 Waiter 并发送
                waiter = self.waiter_registry.register(event.event_id)
                await self.send(event)
                
                # 等待回复
                result = await waiter.wait(timeout)
                return result
                
            except TimeoutError:
                logger.warning(
                    f"Blocking event {event.event_id} timeout "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                
                if attempt == max_retries - 1:
                    # 最后一次尝试失败
                    raise BlockingEventTimeoutError(event.event_id, max_retries)
                
                # 重试前清理 Waiter
                self.waiter_registry.unregister(event.event_id)
                
                # 指数退避
                await asyncio.sleep(2 ** attempt)
```

### 6.2 Hook 层的处理

```python
class HookHandler:
    async def handle_pre_tool_use(self, context: HookContext) -> HookResult:
        """处理 PreToolUse Hook"""
        
        event = create_pre_tool_use_event(context)
        
        try:
            # 发送阻塞事件（带重试）
            replies = await self.outbox.send_blocking(
                event, 
                timeout=30,
                max_retries=3
            )
            
            # 聚合回复
            decision = self.aggregate_decisions(replies)
            
        except BlockingEventTimeoutError as e:
            # 所有重试都超时，回退策略
            logger.error(f"All blocking subscribers timeout: {e}")
            
            # 选项 1：拒绝（保守）
            decision = Decision(
                permission="deny",
                reason="审计节点响应超时，出于安全考虑拒绝操作"
            )
            
            # 选项 2：允许（激进）
            # decision = Decision(
            #     permission="allow",
            #     reason="审计节点响应超时，允许操作继续"
            # )
        
        return HookResult(
            permissionDecision=decision.permission,
            permissionDecisionReason=decision.reason
        )
```

---

## 7. 会话恢复

### 7.1 Backend Session 的恢复

Backend Session 在 Node Runtime 内部运行，节点重启后会话丢失。

#### 恢复策略

| session_scope | 恢复策略 |
|--------------|---------|
| `per-event` | 无需恢复（每次新建） |
| `upstream-session` | 按需重建（事件到达时） |
| `global` | 启动时重建，加载历史上下文（可选） |
| 派发型策略 | 启动时创建最小数量的会话 |

```python
class NodeRuntime:
    async def startup_recovery(self):
        """启动时恢复会话"""
        
        # 1. 恢复全局会话
        for subscription in self.get_global_subscriptions():
            scope = subscription.session_scope
            if scope.startswith("global"):
                # 重建全局会话
                session_id = scope.split(":", 1)[1] if ":" in scope else "global"
                await self.session_manager.get_or_create(
                    session_id=session_id,
                    session_profile=subscription.session_profile
                )
        
        # 2. 为派发型策略创建最小数量的会话
        for subscription in self.get_dispatch_subscriptions():
            min_sessions = subscription.min_conversations
            for i in range(min_sessions):
                session_id = f"auto-{subscription.source_id}-{i}"
                await self.session_manager.get_or_create(
                    session_id=session_id,
                    session_profile=subscription.session_profile
                )
```

### 7.2 Interactive Agent 的重连

Interactive Agent 是独立进程，Node Runtime 崩溃后需要重新连接。

#### 自动重连机制

```python
# Hook Proxy / MCP Server 的重连逻辑
class NodeRuntimeConnection:
    """到 Node Runtime 的连接（带自动重连）"""
    
    def __init__(self, node_id: str, agent_id: str):
        self.node_id = node_id
        self.agent_id = agent_id
        self.socket_path = f"/tmp/mosaic-node-{node_id}.sock"
        self.connection = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
    
    async def connect(self):
        """连接到 Node Runtime"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self.connection = await asyncio.open_unix_connection(
                    self.socket_path
                )
                
                # 发送注册消息
                await self.send_register()
                
                logger.info(f"Connected to Node Runtime {self.node_id}")
                self.reconnect_attempts = 0
                return
                
            except (FileNotFoundError, ConnectionRefusedError) as e:
                self.reconnect_attempts += 1
                backoff = min(2 ** self.reconnect_attempts, 60)
                
                logger.warning(
                    f"Failed to connect to Node Runtime (attempt "
                    f"{self.reconnect_attempts}): {e}. "
                    f"Retrying in {backoff}s"
                )
                
                await asyncio.sleep(backoff)
        
        raise RuntimeError(
            f"Failed to connect to Node Runtime after "
            f"{self.max_reconnect_attempts} attempts"
        )
    
    async def send_with_retry(self, message: dict):
        """发送消息（带重连）"""
        while True:
            try:
                await self.send(message)
                return
            except (ConnectionError, BrokenPipeError):
                logger.warning("Connection lost, reconnecting...")
                await self.connect()
```

---

## 8. 监控与告警

### 8.1 监控指标

```python
class MetricsCollector:
    """收集系统指标"""
    
    def collect_daemon_metrics(self) -> dict:
        return {
            "nodes_total": len(self.node_registry),
            "nodes_running": self.count_by_status("running"),
            "nodes_failed": self.count_by_status("failed"),
            "uptime_seconds": time.time() - self.start_time
        }
    
    def collect_node_metrics(self, node_id: str) -> dict:
        info = self.node_registry[node_id]
        return {
            "status": info['status'],
            "crash_count": info.get('crash_count', 0),
            "uptime_seconds": (datetime.now() - info['start_time']).total_seconds(),
            "last_restart": info.get('last_restart'),
            "pending_events": self.get_pending_events_count(node_id)
        }
```

### 8.2 告警策略

```python
class AlertManager:
    """告警管理"""
    
    async def check_alerts(self):
        """检查告警条件"""
        
        # 1. 节点频繁重启
        for node_id, info in self.node_registry.items():
            if info.get('crash_count', 0) >= 3:
                await self.alert(
                    level="warning",
                    message=f"Node {node_id} has crashed {info['crash_count']} times"
                )
        
        # 2. 节点达到最大重试
        for node_id, info in self.node_registry.items():
            if info['status'] == 'failed':
                await self.alert(
                    level="critical",
                    message=f"Node {node_id} has failed and stopped restarting"
                )
        
        # 3. 事件队列积压
        for node_id in self.node_registry.keys():
            pending = await self.get_pending_events_count(node_id)
            if pending > 1000:
                await self.alert(
                    level="warning",
                    message=f"Node {node_id} has {pending} pending events"
                )
```

---

## 9. CLI 命令

```bash
# 查看 Daemon 状态
ccm daemon status

# 查看所有节点状态
ccm ps

# 查看单个节点详细状态
ccm status worker

# 手动重启节点
ccm restart worker

# 查看节点日志
ccm logs worker --tail 100 --follow

# 查看崩溃历史
ccm history worker

# 清理失败状态
ccm reset worker
```

---

## 10. 总结

### 10.1 恢复层次

| 层级 | 机制 | 恢复时间 |
|------|------|---------|
| Daemon | systemd 自动重启 | 5-10 秒 |
| Node Runtime | Daemon 监控 + 指数退避重启 | 5-60 秒（根据重试次数） |
| Backend Session | 按需重建 | 即时 |
| Interactive Agent | 自动重连 | 2-60 秒（根据重连次数） |

### 10.2 可靠性保证

| 保证 | 机制 |
|------|------|
| 进程监控 | PID 检测 + 可选心跳 |
| 自动重启 | 指数退避 + 最大重试限制 |
| 事件不丢失 | At-least-once + 恢复窗口 |
| 幂等性 | ACK/NACK + 业务逻辑保证 |
| 阻塞事件可靠性 | 超时重试 + 回退策略 |

### 10.3 配置建议

| 场景 | 配置 |
|------|------|
| 生产环境 | restart=always, max-retries=5, recovery-window=300 |
| 开发环境 | restart=on-failure, max-retries=3, recovery-window=60 |
| 测试环境 | restart=no（手动控制） |

---

**文档结束**

