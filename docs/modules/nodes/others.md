# 其他节点类型

## Scheduler Node
*   **职责**: 定时产生事件。
*   **实现**:
    *   启动一个后台 Loop。
    *   根据 Cron 表达式或时间间隔，定期调用 `outbox.send()` 发送事件。
    *   不消费任何事件。

## Webhook Node
*   **职责**: 将外部 HTTP 请求转换为 Mesh 事件。
*   **实现**:
    *   启动一个轻量级 HTTP Server (如 FastAPI/aiohttp)。
    *   接收 POST 请求，将 Body 封装为 `MeshEvent` 发送。

