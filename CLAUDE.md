# 记忆系统操作手册

## 记忆结构

### Chroma 集合
- **集合名称**: `memory_mosaic-project`
- **职责**: 仅查询和使用记忆（绝不写入、修改或删除）

### 记忆分类

#### 1. 长期记忆（6类）

每类长期记忆的 ID 和元数据结构：

| Document ID | 内容 | Metadata |
|------------|------|----------|
| `longterm_user_prefs` | 用户编码风格、技术偏好、工作习惯、沟通风格 | `{"type": "longterm", "category": "user_prefs"}` |
| `longterm_project_overview` | 项目类型、技术栈、目录结构、关键配置 | `{"type": "longterm", "category": "project_overview"}` |
| `longterm_architecture` | 架构模式、设计模式、架构决策及理由 | `{"type": "longterm", "category": "architecture"}` |
| `longterm_tech_knowledge` | 框架/库配置、工具使用、最佳实践 | `{"type": "longterm", "category": "tech_knowledge"}` |
| `longterm_lessons_learned` | 问题-解决方案对比、踩坑经验 | `{"type": "longterm", "category": "lessons_learned"}` |
| `longterm_issues_and_roadmap` | 当前问题、技术债、待办事项、未来规划 | `{"type": "longterm", "category": "issues_and_roadmap"}` |

> **注意**: 每个类别只有一条记录，ID 固定，直接用 ID 获取最高效。

#### 2. 会话记忆

每个会话的元数据格式：

```json
{
  "type": "session",
  "session_id": "xxx",
  "node_id": "mosaic-project",
  "timestamp": "2025-12-17 14:30:25",
  "topic": "会话主题描述"
}
```

---

## 职责边界

### ✅ 我应该做的
- 查询记忆：使用 Chroma 工具查询历史记忆
- 使用记忆：根据记忆提供连贯、个性化的服务

### ❌ 我绝不做的
- 不主动写入 Chroma（add/update/delete documents）
- 不修改或删除记忆
- 不整理或总结记忆用于存储

> **原则**: 记忆整理是 mem 节点的专属职责，我只负责"回忆"

---

## 长期记忆使用方案

### 会话启动阶段

**必查项**（每次会话开始时）：
1. 最近 1-2 个会话记忆（了解上下文连续性）
2. `longterm_user_prefs`（了解用户风格和偏好）
3. `longterm_project_overview`（快速掌握项目背景）

**标准启动流程**（三步并行 + 一步按需）：

```python
# 第一步：获取所有会话的元数据（轻量查询）
chroma_get_documents(
    collection_name="memory_mosaic-project",
    where={"type": "session"},
    include=["metadatas"]  # ids 会自动返回
)

# 第二步：直接用 ID 获取长期记忆（最高效）
chroma_get_documents(
    collection_name="memory_mosaic-project",
    ids=["longterm_user_prefs", "longterm_project_overview"],
    include=["documents", "metadatas"]
)

# 第三步：手动排序会话元数据
# - 按 metadata.timestamp 降序排序
# - 获取最新 1-2 个会话的 ID

# 第四步：按需获取最新会话的详细内容
chroma_get_documents(
    collection_name="memory_mosaic-project",
    ids=["最新的会话ID1", "最新的会话ID2"],
    include=["documents", "metadatas"]
)
```

**关键要点**：
- ✅ 第一、二步可并行执行（互不依赖）
- ✅ 长期记忆用 ID 直接获取（6 个类别 ID 固定）
- ✅ 会话记忆先获取元数据，排序后按需加载详细内容
- ❌ 不要用 `peek_collection`（会加载所有记忆的完整内容）
- ❌ 不要对长期记忆用语义查询（ID 固定，直接获取更快）

### 任务执行阶段

根据任务类型，按需查询相关长期记忆：

#### 场景1：编写新代码/功能开发
**查询顺序**：
1. `longterm_user_prefs` → 确认代码风格偏好
2. `longterm_architecture` → 理解模块划分和设计模式
3. `longterm_tech_knowledge` → 查找相关技术的使用方法
4. `longterm_lessons_learned` → 避免已知的坑

**查询示例**：
- `"用户喜欢的代码组织方式"`
- `"项目使用的认证架构"`
- `"日志框架的配置方法"`

#### 场景2：调试问题/修复Bug
**查询顺序**：
1. `longterm_lessons_learned` → 查找类似问题的解决方案
2. `longterm_tech_knowledge` → 了解相关技术的注意事项
3. `longterm_issues_and_roadmap` → 确认是否为已知问题

**查询示例**：
- `"环境变量相关的错误"`
- `"数据库连接池的问题"`
- `"异步操作的常见陷阱"`

#### 场景3：技术选型/架构决策
**查询顺序**：
1. `longterm_user_prefs` → 了解用户技术偏好
2. `longterm_architecture` → 理解现有架构约束
3. `longterm_tech_knowledge` → 已有技术栈的限制

**查询示例**：
- `"用户对框架的选择倾向"`
- `"项目的扩展性设计原则"`

#### 场景4：规划任务/重构
**查询顺序**：
1. `longterm_issues_and_roadmap` → 了解待办事项和技术债
2. `longterm_architecture` → 理解重构的影响范围
3. `longterm_user_prefs` → 确认用户对重构的态度

**查询示例**：
- `"当前的技术债务"`
- `"需要重构的模块"`
- `"用户对迭代方式的偏好"`

#### 场景5：用户说"像之前那样"
**查询**：
- 使用语义查询搜索会话记忆
- 查询示例：`"之前实现登录功能的方式"`

---

## 查询方法

### 方法1：直接用 ID 获取（推荐用于固定类别）

**适用场景**：
- 获取 6 类长期记忆（ID 固定）
- 获取已知 ID 的会话记忆

```python
# 获取长期记忆（最高效）
chroma_get_documents(
    collection_name="memory_mosaic-project",
    ids=["longterm_user_prefs", "longterm_architecture"],
    include=["documents", "metadatas"]
)

# 获取指定会话
chroma_get_documents(
    collection_name="memory_mosaic-project",
    ids=["session_xxx"],
    include=["documents", "metadatas"]
)
```

**优势**：
- 最快速（无需向量搜索）
- 最精确（直接定位）
- 最简洁（无需复杂过滤条件）

### 方法2：语义查询（用于搜索内容）

**适用场景**：
- 在长期记忆的**内容**中搜索知识片段（如"环境变量相关的错误"）
- 在多条会话记忆中搜索历史（如"之前实现登录功能的方式"）

```python
# 在所有记忆中搜索内容
chroma_query_documents(
    collection_name="memory_mosaic-project",
    query_texts=["数据库连接池的问题"],
    n_results=3
)

# 在特定类别中搜索（需要 $and 运算符）
chroma_query_documents(
    collection_name="memory_mosaic-project",
    query_texts=["用户喜欢的测试框架"],
    n_results=3,
    where={"$and": [{"type": "longterm"}, {"category": "tech_knowledge"}]}
)
```

**where 条件语法**：
- ❌ 错误：`where={"type": "longterm", "category": "user_prefs"}`
- ✅ 正确：`where={"$and": [{"type": "longterm"}, {"category": "user_prefs"}]}`

### 方法3：过滤查询（用于获取特定类型）

**适用场景**：
- 获取所有会话的元数据（用于排序）
- 获取特定类型的所有记忆

```python
# 获取所有会话的元数据（轻量查询）
chroma_get_documents(
    collection_name="memory_mosaic-project",
    where={"type": "session"},
    include=["metadatas"]  # ids 会自动返回，不需要也不能在 include 里指定
)

# 获取所有长期记忆
chroma_get_documents(
    collection_name="memory_mosaic-project",
    where={"type": "longterm"},
    include=["documents", "metadatas"]
)
```

**include 参数说明**：
- ✅ 可选值：`documents, embeddings, metadatas, distances, uris, data`
- ✅ `ids` 总是自动返回，无需指定
- ❌ `include=["metadatas", "ids"]` 会报错

### 查询关键原则

1. **方法选择**：
   - 获取固定类别 → 方法1（直接用 ID）
   - 搜索记忆内容 → 方法2（语义查询）
   - 获取特定类型 → 方法3（过滤查询）

2. **自然语言描述**：语义查询用任务相关的自然语言而非精确关键词

3. **按需查询**：不要一次性查询所有记忆，根据任务需要分阶段查询

4. **优先级**：用户偏好 > 经验教训 > 技术知识

5. **结果数量**：语义查询一般获取 3-5 条相关结果即可

6. **效率优先**：
   - ✅ 启动时：先轻量查询（元数据），再按需加载（详细内容）
   - ✅ 长期记忆：直接用 ID 获取，不用语义查询
   - ❌ 避免：使用 `peek_collection` 或一次性加载所有记忆
