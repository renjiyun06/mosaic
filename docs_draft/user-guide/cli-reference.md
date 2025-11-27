# Mosaic CLI 使用手册

> **文档用途**: Mosaic 命令行工具的完整参考手册  
> **适用对象**: 终端用户、开发者、运维人员

---

## 1. 快速开始

Mosaic 是一个基于事件驱动的多智能体与组件协作网格。通过命令行工具 `mosaic`，你可以轻松创建、编排和运行多个智能体节点以及调度器、Webhook 等系统组件节点。

### 典型工作流

```bash
# 1. 初始化一个新的 Mesh 实例
mosaic init --mesh-id dev-mesh

# 2. 创建节点
# 创建一个工作节点 (Worker) 和一个审计节点 (Auditor)
# 注意：对于 cc (Claude Code) 类型的节点，必须指定工作区路径
mosaic create worker --type cc --workspace ./worker-workspace
mosaic create auditor --type cc --workspace ./auditor-workspace

# 3. 编排网络 (建立订阅)
# 让 Auditor 拦截 Worker 的所有工具调用 (!PreToolUse 表示阻塞)
# 使用默认的 mirroring 策略（为 Worker 的每个会话建立对应的审计会话）
mosaic sub auditor worker "!PreToolUse" --strategy mirroring

# 4. 启动 Mesh 环境
# 启动守护进程，它会自动拉起所有配置为后台运行的节点（如 Auditor）
mosaic start

# 5. 运行工作节点 (开始交互)
# 这将打开 Claude Code 的交互界面，你可以指挥它工作
mosaic chat worker
```

---

## 2. 命令参考

### 2.1 基础环境管理 (Mesh)

管理 Mesh 实例的生命周期。每个 Mesh 是一个独立的隔离环境。

*   **初始化环境**
    ```bash
    mosaic init [--mesh-id <id>]
    ```
    在当前用户目录下创建 `~/.mosaic/<id>/` 结构，初始化控制数据库。如果不指定 ID，默认为 `default`。

*   **重置环境**
    ```bash
    mosaic reset [--force]
    ```
    清空当前 Mesh 的所有数据（节点、事件、日志）。慎用！

### 2.2 节点管理 (Node)

管理节点的增删改查。

*   **创建节点**
    ```bash
    mosaic create <node_id> --type <type> [--mesh-id <id>] [options]
    ```
    *   `<type>`: 节点类型，如 `cc` (Claude Code), `scheduler`。
    *   `--workspace <path>`: 指定节点的工作区（对 `cc` 节点必须）。
    *   `--config <key>=<value>`: 传递节点特定的配置参数。
    
    示例: 
    ```bash
    # 创建 CC 节点
    mosaic create worker --type cc --workspace ./projects/app1
    
    # 创建 Scheduler 节点（带额外配置）
    mosaic create cron --type scheduler --config interval=60
    ```

*   **列出节点**
    ```bash
    mosaic list [--mesh-id <id>]
    ```
    显示所有已注册的节点及其静态配置信息。

*   **查看运行状态**
    ```bash
    mosaic ps [--mesh-id <id>]
    ```
    显示所有节点的实时运行状态（PID, Uptime, Status）。

*   **查看节点详情**
    ```bash
    mosaic status <node_id> [--mesh-id <id>]
    ```
    显示指定节点的详细信息，包括订阅关系、最近错误日志等。

*   **删除节点**
    ```bash
    mosaic delete <node_id> [--mesh-id <id>]
    ```
    删除节点及其相关的所有订阅关系。

### 2.3 网络编排 (Topology)

定义节点间的事件流向和协作关系。

*   **订阅事件**
    ```bash
    mosaic sub <subscriber> <publisher> "<pattern>" [--mesh-id <id>] [options]
    ```
    让 `<subscriber>` 监听 `<publisher>` 产生的事件。
    *   `pattern`: 事件模式 (如 `*`, `PreToolUse`, `!PreToolUse` 表示阻塞)。
    *   `--strategy <name>`: 会话路由策略 (默认: `mirroring`)。
        *   `mirroring`: 镜像模式，跟随上游会话。
        *   `tasking`: 任务模式，一事一议。
        *   `aggregation`: 聚合模式，多源汇聚。
        *   `stateful`: 有状态模式，基于上下文生命周期。
    *   `--param <key>=<value>`: 策略特定的参数。

    示例:
    ```bash
    # 1. 基础审计 (镜像模式，默认)
    # Auditor 会为 Worker 的每个会话建立对应的审计会话
    mosaic sub auditor worker "!PreToolUse" --strategy mirroring

    # 2. 独立分析 (任务模式)
    # 对每个 PushEvent 启动一个独立的会话进行分析
    mosaic sub analyzer git_watcher "PushEvent" --strategy tasking

    # 3. 日志聚合 (聚合模式)
    # 将所有 Worker 的日志汇聚到一个 "central_log" 会话，每 20 条处理一次
    mosaic sub logger worker "*" \
        --strategy aggregation \
        --param name=central_log \
        --param buffer_size=20
    ```

*   **取消订阅**
    ```bash
    mosaic unsub <subscriber> <publisher> "<pattern>" [--mesh-id <id>]
    ```
    移除指定的订阅关系。

*   **查看拓扑**
    ```bash
    mosaic topology [--mesh-id <id>] [--graph]
    ```
    以列表或图形化方式展示当前网络的订阅关系图。

### 2.4 运行与交互 (Runtime)

*   **交互式会话**
    ```bash
    mosaic chat <node_id> [--mesh-id <id>]
    ```
    连接到指定节点的交互式会话。
    *   如果节点尚未运行，该命令会以交互模式启动它（如果是 CC 节点，将打开 REPL 界面）。
    *   如果节点已在后台运行，该命令会附加到其会话流中（支持实时查看和干预）。
    *   这是用户与智能体节点交互的主要方式。

*   **编程/培训模式**
    ```bash
    mosaic program <node_id> [--mesh-id <id>]
    ```
    ... (说明不变)


---

## 3. 环境变量

可以通过环境变量配置全局行为，避免重复输入参数。

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `MOSAIC_MESH_ID` | 当前操作的 Mesh ID | `default` |
| `MOSAIC_HOME` | 数据存储根目录 | `~/.mosaic` |
| `MOSAIC_LOG_LEVEL` | CLI 输出日志级别 | `INFO` |

示例：
```bash
export MOSAIC_MESH_ID=prod-mesh
mosaic ps  # 查看 prod-mesh 的状态
```

