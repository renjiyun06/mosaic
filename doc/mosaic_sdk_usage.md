# Mosaic SDK 使用指南

## 核心能力

Mosaic SDK 的核心能力是**赋予 node 语义调用的能力**。

你可以用任意有语义含义的方法名调用 node，无需预先定义 API。Node 会理解方法名的语义含义，结合参数和指令，执行相应的任务。

## 基本用法

### 连接到 Node

```python
from mosaic.v2.sdk.client import MosaicSDK

async with MosaicSDK(
    username="user",
    password="pass",
    base_url="http://localhost:8000",
    auto_login=True
) as sdk:
    async with sdk.get_mosaic("mosaic-name").get_node("node-id").connect() as node:
        # 语义调用 node
        result = await node.method_name(param1="value1", _instruction="具体指令")
```

**重要特性：**
- 在同一个 `with` 块中，对同一个 node 的所有语义调用都将发送到同一个会话中，保持上下文连贯
- **必须使用关键字参数**：语义调用只支持关键字参数，因为参数名本身就是语义信息的一部分，帮助 node 理解每个参数的用途
- **特殊参数**：
  - `_instruction`：提供详细的执行指令（可选）
  - `_return_schema`：指定返回结果必须遵循的 JSON Schema，确保返回格式可预测（可选）
  - `_timeout`：指定该调用的超时时间（单位：秒），默认为 60 秒（可选）

### 语义调用示例

```python
# 示例1: 统计单词
result = await node.count_words(
    text="Hello, world!, hello, hello",
    _instruction="给出各个单词的个数, 返回一个字典"
)
# 返回: {"hello": 3, "world": 1}

# 示例2: 分析数据
result = await node.analyze_user_behavior(
    user_data={"clicks": 150, "time_spent": 3600},
    _instruction="分析用户活跃度并给出评分"
)

# 示例3: 使用 _return_schema 约束返回格式
result = await node.analyze_sentiment(
    text="这个产品很好用，但是价格有点贵",
    _return_schema={
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "score": {"type": "number", "minimum": 0, "maximum": 1},
            "keywords": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["sentiment", "score", "keywords"]
    }
)
# 返回格式保证符合 schema，程序可以安全地访问字段
print(f"情感: {result['sentiment']}, 分数: {result['score']}")

# 示例4: 使用 _timeout 延长超时时间（适合耗时较长的任务）
result = await node.write_short_story(
    theme="未来世界的冒险",
    style="科幻悬疑",
    _timeout=180,  # 3分钟超时，适合生成长文本等耗时任务
    _instruction="创作一篇800-1000字的短篇小说"
)
```

**核心特性：**
- **方法名**（如 `count_words`、`analyze_user_behavior`）表达调用的语义
- **参数**传递具体数据
- **_instruction** 参数（可选）：提供详细的执行指令
- **_return_schema** 参数（可选）：指定返回结果必须遵循的 JSON Schema，确保返回数据结构可预测，便于程序处理
- **_timeout** 参数（可选）：指定超时时间（单位：秒），默认 60 秒，适合调整耗时较长的任务
- Node 理解语义并返回符合要求的结果
