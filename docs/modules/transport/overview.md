# Transport 模块

## 职责
提供 Mosaic 数据平面的具体实现，负责事件的物理存储、传输和进程间通知。

## SQLite 实现 (默认)

### 架构
*   **存储**: 每个 Mesh 拥有独立的 SQLite 数据库 `~/.mosaic/<mesh_id>/events.db`。
*   **通知**: 使用 Unix Domain Socket (UDS) 进行进程间唤醒。

### 组件
*   **SQLiteTransportBackend**: 实现 `TransportBackend` 接口。
*   **EventRepository**: 封装 SQLite 操作，管理 `event_queue` 表。
    *   支持 WAL 模式以提高并发性能。
    *   实现恢复窗口查询逻辑。
*   **SignalClient/SignalListener**:
    *   `SignalListener`: 在 `~/.mosaic/<mesh_id>/sockets/<node_id>.sock` 监听单字节信号。
    *   `SignalClient`: 向目标节点的 Socket 发送信号。

## 扩展性
该模块设计为可插拔。未来可增加 `KafkaTransportBackend` 或 `RedisTransportBackend`，只需实现 `TransportBackend` 接口即可。

