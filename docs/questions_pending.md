# 待确认问题记录

## 1. Program 模式的持久化机制
**现状**: 文档提到 Program 模式用于"离线培训"，配置会被持久化。
**疑问**: 
- 是否有标准化的配置格式存储在 `mosaic.db` 中？
- 运行时如何加载这些"非结构化"的培训成果？

## 2. claude-agent-sdk
**现状**: 文档多次提及 `claude-agent-sdk` 用于 Backend Session。
**疑问**: 
- 这是一个现有的库还是需要我们开发的内部模块？
- 如果是外部库，它的 API 签名是什么？

## 3. Interactive Agent IPC 协议
**现状**: Interactive Agent 是独立进程，通过 IPC 与 Node Process 通信。
**疑问**: 
- IPC 的具体协议是什么？（JSON-RPC over UDS?）
- 鉴权机制如何设计？

## 4. 工作区 (Workspace) 共享
**现状**: "CC 节点必须有工作区"。
**疑问**: 
- 多个节点是否可以共享同一个物理工作区目录？
- 如果共享，`.claude/settings.json` 等配置文件如何隔离？

## 5. 订阅链 (Subscription Chain)
**现状**: `run_interactive` 需要查询订阅链来启动后台节点。
**疑问**: 
- 订阅链的递归方向是 Upstream 还是 Downstream？
- 如何处理环状依赖？
