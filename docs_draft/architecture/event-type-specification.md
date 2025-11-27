# 事件类型规范与管理机制 (Event Type Specification)

> **文档状态**: Draft
> **最后更新**: 2025-11-26
> **核心主题**: 定义系统中的“语言”——事件类型

## 1. 核心理念

在 Mosaic 网格中，**事件类型 (Event Type)** 不仅仅是一个字符串标签，它是连接异构智能体（Agents）与组件（Components）的**语义契约**。

由于系统的核心消费者是 LLM（大型语言模型），事件类型的设计必须遵循 **LLM-Native** 原则：
1.  **自描述性**：事件类型必须携带足够的自然语言描述和结构定义，以便直接注入到 LLM 的 System Prompt 中。
2.  **契约化**：它定义了生产者承诺提供的数据格式，以及消费者可以预期的语义含义。

---

## 2. 事件类型标识符 (Event Type Identifier)

为了在分布式环境中避免冲突并明确归属，事件类型采用分层命名空间结构。

### 2.1 命名格式

```text
<namespace>:<category>.<event_name>
```

*   **namespace**: 顶级域，通常代表插件包、组织或核心系统。
    *   `mosaic` (核心系统事件)
    *   `claude` (Claude Code 相关事件)
    *   `user` (用户自定义)
*   **category**: 功能分类。
    *   `lifecycle` (生命周期)
    *   `hook` (钩子)
    *   `audit` (审计)
*   **event_name**: 具体的动作或状态变更，建议使用“名词+动词”或“动词+名词”的驼峰命名法。

### 2.2 示例

*   `mosaic:system.NodeStarted` - 节点启动事件
*   `claude:hook.PreToolUse` - 工具使用前钩子
*   `git:commit.Created` - Git 提交创建事件

---

## 3. 事件类型定义 (Event Type Definition, ETD)

一个完整的事件类型定义包含以下元数据，这些数据存储在控制平面的元数据库中。

### 3.1 数据结构

| 字段 | 类型 | 说明 | 用途 |
| :--- | :--- | :--- | :--- |
| **identifier** | String | 全局唯一的事件类型标识符 (见 2.1) | 路由、订阅匹配 |
| **description** | String | **自然语言描述**，详细解释事件触发的时机和含义 | **注入 LLM Prompt**，让 AI 理解语境 |
| **schema** | JSON Schema | 事件 Payload 的严格结构定义 | 数据校验、代码生成 |
| **examples** | List[JSON] | 典型的 Payload 示例 | **注入 LLM Prompt**，作为 Few-Shot 样本 |
| **version** | String | 版本号 (SemVer)，如 `1.0.0` | 处理兼容性演进 |

### 3.2 定义示例 (YAML 风格)

```yaml
identifier: "claude:hook.PreToolUse"
version: "1.0.0"
description: >
  当 Claude Code 尝试执行任何 MCP 工具（如读写文件、执行命令）之前触发。
  接收此事件的节点可以审查工具调用参数，并决定是否允许执行。
schema:
  type: object
  properties:
    tool_name: { type: string }
    tool_args: { type: object }
    thought_chain: { type: string }
examples:
  - tool_name: "bash"
    tool_args: { command: "ls -la" }
```

---

## 4. 管理机制：基于能力的注册

系统不维护一张静态的“全局事件表”，而是采用**去中心化的能力声明**机制。事件类型是依附于**节点类型 (Node Type)** 存在的。

### 4.1 生产者声明 (Producer Declaration)
当一个新的节点类型（如 `GitMonitor`）被引入系统时，它必须在注册时声明它**拥有产生哪些事件类型的能力**。

*   **所有权原则**：通常由“拥有者”节点负责定义事件的 Schema 和 Description。
*   **注册时机**：节点类型安装或启动时。

### 4.2 消费者引用 (Consumer Reference)
消费者节点（如 `Auditor`）在订阅时，实际上是订阅了某个**契约**。消费者不需要重新定义事件，只需声明它能理解（Consume）该类型。

### 4.3 冲突处理
如果两个不同的节点类型声明了**同一个**事件标识符（如 `claude:hook.PreToolUse`），系统必须校验它们的 Definition 是否完全一致（Schema 和语义）。如果不一致，注册将失败，以保证语义的全局唯一性。

---

## 5. 运行时流程：语义注入

这是 Mosaic 区别于传统消息队列的核心特性。

1.  **启动阶段**：AI 节点（如 Auditor）启动，连接到 Mesh。
2.  **自省 (Introspection)**：节点查询自身订阅列表，获取所有已订阅的事件类型 ID。
3.  **语义拉取**：Runtime 向控制平面请求这些 ID 对应的 **Description** 和 **Examples**。
4.  **Prompt 构建**：Runtime 将这些信息组装成系统提示词：
    > "你当前订阅了 `PreToolUse` 事件。该事件意味着......这里有一个数据示例......"
5.  **决策循环**：AI 依靠注入的上下文，准确理解收到的 JSON 数据并做出决策。

---

## 6. 待定问题与探讨 (Open Questions)

在梳理上述规范时，暴露出了以下深层次的架构疑问，需要进一步讨论：

### Q1: 标准库与自定义扩展的边界？
*   **现状**：某些事件（如 `PreToolUse`）似乎是系统级的核心契约。如果依靠第三方节点（如 `CCNode`）来定义它，一旦该节点未安装，整个审计系统的契约就失效了。
*   **疑问**：是否需要一个独立于节点的 **"Core Schema Registry"**？即某些核心事件类型是预置在系统中的，不依赖任何具体节点的注册。

### Q2: Schema 校验的执行者？
*   **现状**：文档未明确 Payload 是否会被强制校验。
*   **疑问**：如果生产者发送的数据不符合它自己声明的 Schema：
    *   Runtime 应该直接丢弃该事件并报错吗？
    *   还是仅作为元数据参考，由消费者自己处理异常？
    *   考虑到 AI 的鲁棒性，强制校验可能导致系统过于脆弱；但不校验可能导致 Prompt 注入攻击或解析错误。

### Q3: 版本控制策略 (Versioning)？
*   **现状**：不同版本的节点可能存在于同一个 Mesh 中。
*   **疑问**：如果 `PreToolUse` 从 v1 升级到 v2（字段改名）：
    *   订阅 v1 的消费者还能收到 v2 的事件吗？
    *   事件标识符是否应该包含版本？如 `claude:hook.PreToolUse@v1`？

### Q4: 跨 Mesh 的类型共享？
*   **现状**：每个 Mesh 是隔离的。
*   **疑问**：事件定义是否应该在系统级别全局共享？如果我在 Mesh A 定义了 `MyEvent`，在 Mesh B 创建同类节点时，是否需要重新注册一遍？这关系到 `control.db` 的作用域是 Mesh 级还是 Global 级。

