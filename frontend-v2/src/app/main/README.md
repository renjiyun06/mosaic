# Mosaic Main 页面 - 代码重构文档

## 📁 目录结构概览

```
src/app/main/
├── page.tsx                    # 页面入口文件
├── components/                 # UI 组件目录
├── hooks/                      # 自定义 React Hooks
├── types/                      # TypeScript 类型定义
├── utils/                      # 工具函数
└── constants/                  # 常量和 Mock 数据
```

---

## 📄 `page.tsx` - 页面入口

**文件路径**: `src/app/main/page.tsx`

**作用**: Next.js 页面入口，负责初始化 ReactFlow Provider 和渲染主画布组件

**内容**:
```typescript
export default function MainPage() {
  return (
    <ReactFlowProvider>
      <InfiniteCanvas />
    </ReactFlowProvider>
  )
}
```

**职责**:
- 提供 ReactFlow 上下文
- 渲染 InfiniteCanvas 组件

---

## 📦 `components/` - UI 组件目录

存放所有 UI 组件，按功能模块划分为 6 个子目录。

### 1️⃣ `components/canvas/` - 画布核心组件

**作用**: 存放画布的主要 UI 组件和布局元素

#### 文件清单:

| 文件名 | 作用 | 导出内容 |
|--------|------|----------|
| `InfiniteCanvas.tsx` | **主画布组件**，整合所有功能模块 | `InfiniteCanvas` 组件 |
| `TopologyLegend.tsx` | 拓扑图图例（右下角） | `TopologyLegend` 组件 |
| `CanvasContextMenu.tsx` | 画布右键菜单 | `CanvasContextMenu` 组件 |
| `TopRightActions.tsx` | 右上角快捷操作按钮 | `TopRightActions` 组件 |
| `index.ts` | 统一导出所有组件 | - |

#### 详细说明:

**`InfiniteCanvas.tsx`** (主组件)
- 整合所有 Hooks（Mosaic 管理、节点管理、画布状态、键盘快捷键）
- 渲染 ReactFlow 画布
- 管理所有对话框和侧边栏的显示状态
- 处理 ReactFlow 事件（节点变化、边变化、连接）

**`TopologyLegend.tsx`**
- 显示连接类型的颜色图例
- 仅在拓扑模式开启时显示

**`CanvasContextMenu.tsx`**
- 画布空白处右键菜单
- 使用 Radix UI ContextMenu 组件
- 自动拦截浏览器默认右键菜单
- 提供快捷操作：
  - Create Node - 创建新节点
  - Show Connections - 显示连接列表
  - Show/Hide Topology - 切换拓扑连接线显示
- 自动边界检测，确保菜单不会超出视口
- 赛博朋克玻璃态风格（青色霓虹光效）
- 菜单项分组（使用分隔线）

**`TopRightActions.tsx`**
- 右上角固定位置的快捷操作按钮组
- 两个圆形按钮：
  - Plus 图标 - 创建节点（提示：Right-click）
  - Command 图标 - 打开命令面板（提示：⌘K）
- 玻璃态设计 + 青色霓虹悬停效果
- Hover 显示功能名称和快捷键提示
- Framer Motion 动画（缩放交互）
- 入场动画：从右侧滑入 + 淡入

---

### 2️⃣ `components/nodes/` - 节点组件

**作用**: 存放节点卡片和连接线的组件

#### 文件清单:

| 文件名 | 作用 | 导出内容 |
|--------|------|----------|
| `CollapsedNodeCard.tsx` | 收起状态的节点卡片（小卡片） | `CollapsedNodeCard` 组件 |
| `ExpandedNodeCard.tsx` | 展开状态的节点卡片（大卡片，含聊天界面） | `ExpandedNodeCard` 组件 |
| `CreateNodeCard.tsx` | 创建节点的表单对话框 | `CreateNodeCard` 组件 |
| `AnimatedEdge.tsx` | 自定义动画连接线 | `AnimatedEdge` 组件, `edgeTypes` 对象 |
| `index.ts` | 统一导出 | - |

#### 详细说明:

**`CollapsedNodeCard.tsx`**
- 显示节点基本信息（ID、类型、状态）
- 显示 Active Sessions 数量（v1.3 优化：移除 Messages 和 Activity）
- 显示入站/出站连接数量徽章
- 4 个连接点（Handle）：上下左右，青色边框，Hover 放大 1.5 倍
- 动态节点类型图标（Bot, Mail, Clock, Layers）
- 点击展开节点
- 提供启动/停止/设置按钮

**`ExpandedNodeCard.tsx`**
- 左侧显示会话列表
- 右侧显示聊天界面
- 4 个连接点（Handle）：上下左右，青色边框，Hover 放大 1.5 倍
- 支持选择会话查看消息
- 支持发送消息（输入框 + 发送按钮）
- 点击最小化按钮收起节点

**`CreateNodeCard.tsx`**
- 输入节点 ID
- 选择节点类型（Claude Code、Email、Scheduler、Aggregator）
- 自动启动开关
- 创建/取消按钮

**`AnimatedEdge.tsx`**
- 自定义 ReactFlow 边组件
- 根据事件类型显示不同颜色
- 粒子动画效果（3 秒循环）
- 显示事件类型标签（使用 EdgeLabelRenderer）
- 显示订阅数量徽章（青色）
- 支持右键菜单（透明 hitbox，宽度 20px）
- Hover 时连接线变青色发光
- 拓扑模式关闭时仍然可交互（透明但可点击）

---

### 3️⃣ `components/mosaic/` - Mosaic 管理组件

**作用**: 存放 Mosaic 实例管理相关的组件

#### 文件清单:

| 文件名 | 作用 | 导出内容 |
|--------|------|----------|
| `MosaicSidebar.tsx` | 左侧 Mosaic 切换侧边栏 | `MosaicSidebar` 组件 |
| `MosaicDialog.tsx` | 创建/编辑 Mosaic 的对话框 | `MosaicDialog` 组件 |
| `index.ts` | 统一导出 | - |

#### 详细说明:

**`MosaicSidebar.tsx`**
- 固定在左侧，宽度 80px
- 显示所有 Mosaic 实例的首字母图标
- 运行状态指示灯（绿色脉冲动画）
- Hover 显示详细信息（使用 Radix UI Tooltip，自动 Portal 渲染）
- 右键上下文菜单（使用 Radix UI ContextMenu，自动边界检测）
  - 启动/停止 Mosaic（根据状态动态显示）
  - 编辑 Mosaic 信息
  - 删除 Mosaic（有节点时禁用）
- 底部创建新 Mosaic 按钮
- 技术实现：
  - `@radix-ui/react-context-menu` - 右键菜单（自动拦截浏览器默认菜单）
  - `@radix-ui/react-tooltip` - Hover 提示（Portal 渲染，不影响滚动条）
  - `framer-motion` - 动画效果
  - 自动边界检测，确保菜单不会超出视口

**`MosaicDialog.tsx`**
- 支持创建和编辑两种模式
- 输入 Mosaic 名称（必填，最多 100 字符）
- 输入描述（可选，最多 500 字符）
- 赛博朋克风格的玻璃态设计

---

### 4️⃣ `components/connections/` - 连接管理组件

**作用**: 存放节点连接和订阅相关的组件

#### 文件清单:

| 文件名 | 作用 | 导出内容 |
|--------|------|----------|
| `ConnectionsSidebar.tsx` | 右侧连接详情侧边栏 | `ConnectionsSidebar` 组件 |
| `ConnectionConfigPanel.tsx` | 连接配置浮动面板 | `ConnectionConfigPanel` 组件 |
| `EdgeContextMenu.tsx` | 连接线右键菜单 | `EdgeContextMenu` 组件 |
| `SubscriptionManagementPanel.tsx` | 订阅管理侧边栏 | `SubscriptionManagementPanel` 组件 |
| `index.ts` | 统一导出 | - |

#### 详细说明:

**`ConnectionsSidebar.tsx`**
- 从右侧滑入的侧边栏
- 显示所有连接的详细信息
- 每个连接显示：源节点 → 事件类型 → 目标节点
- 支持关闭和滚动
- 空状态提示

**`ConnectionConfigPanel.tsx`** (v1.3 新增)
- 拖拽创建连接后弹出的配置面板
- 居中浮动显示，玻璃态 + 青色霓虹边框
- 配置项：
  - 会话对齐策略（3 选 1）：Mirroring / Tasking / Agent-Driven
  - 连接描述（可选，最多 500 字符）
- 单选按钮带圆形指示器和描述
- 弹簧动画入场（scale 0.8 → 1）
- 黑色半透明背景遮罩

**`EdgeContextMenu.tsx`** (v1.3 新增)
- 右键点击连接线弹出的菜单
- 使用 Radix UI ContextMenu
- 菜单项：
  - View Subscriptions（显示订阅数量徽章）
  - Add Subscription
  - Edit Connection
  - Delete Connection（红色高亮）
- 显示连接信息（源 → 目标）
- 自动边界检测，防止超出视口
- 赛博朋克玻璃态风格

**`SubscriptionManagementPanel.tsx`** (v1.3 新增)
- 管理特定连接的订阅
- 从右侧滑入（480px 宽）
- 显示连接信息和订阅列表
- 每个订阅显示：
  - 事件类型（彩色渐变徽章，13 种）
  - 描述文本
  - 创建日期
  - 编辑/删除按钮
- 顶部 Add Subscription 按钮
- 空状态提示
- 左侧青色霓虹边框

---

### 5️⃣ `components/command/` - 命令面板组件

**作用**: 存放命令面板相关的组件

#### 文件清单:

| 文件名 | 作用 | 导出内容 |
|--------|------|----------|
| `CommandPalette.tsx` | 命令面板（Cmd+K 触发） | `CommandPalette` 组件 |
| `index.ts` | 统一导出 | - |

#### 详细说明:

**`CommandPalette.tsx`**
- 使用 `cmdk` 库实现
- 支持搜索和快捷键
- 显示操作列表（创建节点、创建连接、打开终端）
- 显示节点列表
- 键盘导航支持

---

### 6️⃣ `components/shared/` - 共享组件

**作用**: 存放可复用的通用组件

#### 文件清单:

| 文件名 | 作用 | 导出内容 |
|--------|------|----------|
| `LoadingScreen.tsx` | 加载屏幕 | `LoadingScreen` 组件 |
| `AmbientParticles.tsx` | 背景环境粒子动画 | `AmbientParticles` 组件 |
| `index.ts` | 统一导出 | - |

#### 详细说明:

**`LoadingScreen.tsx`**
- 在加载 Mosaics 时显示
- 显示加载动画（旋转的图标）
- 显示"Loading Mosaics..."文本

**`AmbientParticles.tsx`**
- 背景装饰性动画效果
- 20 个随机移动的青色粒子
- 使用 Framer Motion 实现动画

---

## 🪝 `hooks/` - 自定义 Hooks

**作用**: 存放可复用的 React Hooks，封装业务逻辑和状态管理

### 文件清单:

| 文件名 | 作用 | 主要功能 |
|--------|------|----------|
| `useMosaicManagement.ts` | Mosaic 管理 Hook | CRUD 操作、状态管理、自动加载 |
| `useNodeManagement.ts` | 节点管理 Hook | 节点/连接加载、创建、展开/收起 |
| `useCanvasState.ts` | 画布 UI 状态 Hook | 对话框、侧边栏、拓扑显示状态 |
| `useKeyboardShortcuts.ts` | 键盘快捷键 Hook | Cmd+K、Escape 监听 |
| `index.ts` | 统一导出 | - |

### 详细说明:

#### **`useMosaicManagement.ts`**

**返回值**:
```typescript
{
  mosaics: MosaicOut[]                    // 所有 Mosaic 列表
  currentMosaicId: number | null          // 当前选中的 Mosaic ID
  currentMosaic: MosaicOut | null         // 当前选中的 Mosaic 对象
  loadingMosaics: boolean                 // 是否正在加载
  createMosaicOpen: boolean               // 创建对话框是否打开
  setCreateMosaicOpen: (open: boolean)    // 设置创建对话框状态
  editingMosaic: MosaicOut | null         // 正在编辑的 Mosaic
  setEditingMosaic: (mosaic: MosaicOut | null)  // 设置编辑状态
  handleCreateMosaic: (name, description) // 创建 Mosaic
  handleEditMosaic: (id, name, description)     // 编辑 Mosaic
  handleDeleteMosaic: (mosaic)            // 删除 Mosaic
  handleToggleMosaicStatus: (mosaic)      // 启动/停止 Mosaic
  handleSwitchMosaic: (id)                // 切换当前 Mosaic
}
```

**功能**:
- 加载所有 Mosaic 实例
- 自动选中第一个运行中的 Mosaic
- 提供 CRUD 操作函数
- 管理对话框状态

---

#### **`useNodeManagement.ts`**

**参数**: `currentMosaicId: number | null`

**返回值**:
```typescript
{
  apiNodes: NodeOut[]                     // API 返回的节点数据
  apiConnections: ConnectionOut[]         // API 返回的连接数据
  loadingNodes: boolean                   // 是否正在加载节点
  nodes: Node[]                           // ReactFlow 节点数组
  edges: Edge[]                           // ReactFlow 边数组
  setNodes: Dispatch<SetStateAction<Node[]>>    // 更新节点
  setEdges: Dispatch<SetStateAction<Edge[]>>    // 更新边
  handleCreateNode: (nodeData)            // 创建节点
  toggleNodeExpansion: (nodeId)           // 切换节点展开/收起
}
```

**功能**:
- 监听 `currentMosaicId` 变化，自动加载节点和连接
- 将 API 数据转换为 ReactFlow 格式
- 提供创建节点和切换展开状态的函数
- 自动初始化节点的事件处理函数

---

#### **`useCanvasState.ts`**

**返回值**:
```typescript
{
  commandOpen: boolean                    // 命令面板是否打开
  setCommandOpen: (open: boolean)         // 设置命令面板状态
  createNodeOpen: boolean                 // 创建节点对话框是否打开
  setCreateNodeOpen: (open: boolean)      // 设置创建节点对话框状态
  connectionsSidebarOpen: boolean         // 连接侧边栏是否打开
  setConnectionsSidebarOpen: (open: boolean)  // 设置连接侧边栏状态
  showTopology: boolean                   // 是否显示拓扑连接线
  setShowTopology: (show: boolean)        // 设置拓扑显示状态
  toggleTopology: () => void              // 切换拓扑显示
}
```

**功能**:
- 管理所有对话框和侧边栏的打开/关闭状态
- 管理拓扑连接线的显示/隐藏

---

#### **`useKeyboardShortcuts.ts`**

**参数**:
```typescript
{
  onOpenCommand: () => void               // 打开命令面板回调
  onCloseCommand: () => void              // 关闭命令面板回调
}
```

**功能**:
- 监听 Cmd+K / Ctrl+K：打开命令面板
- 监听 Escape：关闭命令面板

---

## 🏷️ `types/` - 类型定义

**作用**: 存放 TypeScript 类型和接口定义

### 文件清单:

| 文件名 | 作用 |
|--------|------|
| `canvas.types.ts` | 画布和节点相关的类型定义 |
| `index.ts` | 统一导出所有类型 |

### 详细说明:

#### **`canvas.types.ts`**

定义的类型:

```typescript
// 会话数据类型
interface Session {
  id: string
  topic: string
  lastActivity: string
  messageCount: number
  status: "active" | "idle"
}

// 节点连接类型
interface NodeConnection {
  from: string
  to: string
  eventType: string
}

// 聊天消息类型
interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
}

// 节点类型配置
interface NodeTypeConfig {
  value: string
  label: string
  icon: any
  color: string
}

// 事件类型颜色配置
interface EventTypeColor {
  stroke: string
  fill: string
  text: string
}
```

---

## 🛠️ `utils/` - 工具函数

**作用**: 存放纯函数工具，提供数据转换和计算功能

### 文件清单:

| 文件名 | 作用 |
|--------|------|
| `colorHelpers.ts` | 颜色相关工具函数 |
| `nodeHelpers.ts` | 节点相关辅助函数 |
| `index.ts` | 统一导出 |

### 详细说明:

#### **`colorHelpers.ts`**

**导出函数**:

```typescript
// 根据事件类型获取颜色配置
getEventTypeColor(eventType: string): EventTypeColor

// 拓扑图图例项
LEGEND_ITEMS: Array<{
  label: string
  color: string
  eventType: string
}>
```

**支持的事件类型**:
- `node_message` → 青色 (#22d3ee)
- `system_message` → 紫色 (#a855f7)
- `task_complete` → 绿色 (#10b981)

---

#### **`nodeHelpers.ts`**

**导出函数**:

```typescript
// 计算节点的入站/出站连接数
getConnectionsForNode(
  nodeId: string,
  connections: ConnectionOut[]
): {
  incoming: ConnectionOut[]
  outgoing: ConnectionOut[]
  incomingCount: number
  outgoingCount: number
}

// 将 API 节点数据转换为 ReactFlow 节点格式
transformApiNodesToFlowNodes(
  apiNodes: NodeOut[]
): Node[]

// 根据节点 ID 获取节点名称
getNodeName(
  nodeId: string,
  nodes: Node[]
): string
```

---

## 📊 `constants/` - 常量和 Mock 数据

**作用**: 存放常量配置和模拟数据

### 文件清单:

| 文件名 | 作用 |
|--------|------|
| `mockData.ts` | Mock 数据（会话、消息、连接） |
| `nodeTypes.ts` | 节点类型配置 |
| `index.ts` | 统一导出 |

### 详细说明:

#### **`mockData.ts`**

**导出数据**:

```typescript
// Mock 会话数据（按节点 ID 分组）
mockSessions: Record<string, Session[]>

// Mock 消息数据（按会话 ID 分组）
mockMessages: Record<string, ChatMessage[]>

// Mock 连接数据
mockConnections: NodeConnection[]
```

**用途**: 用于开发和测试，模拟节点的会话和消息数据

---

#### **`nodeTypes.ts`**

**导出数据**:

```typescript
// 节点类型配置数组
NODE_TYPE_CONFIG: NodeTypeConfig[] = [
  { value: "claude_code", label: "Claude Code", icon: Terminal, color: "cyan" },
  { value: "email", label: "Email", icon: MessageSquare, color: "blue" },
  { value: "scheduler", label: "Scheduler", icon: Activity, color: "purple" },
  { value: "aggregator", label: "Aggregator", icon: Network, color: "emerald" },
]
```

**用途**: 在创建节点时使用，提供节点类型选项

---

## 📦 模块依赖关系

```
┌─────────────────────────────────────────┐
│           page.tsx (入口)                │
│        ↓ imports                        │
│   InfiniteCanvas                        │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│       InfiniteCanvas.tsx                │
│        ↓ imports                        │
│   - Hooks (全部 4 个)                    │
│   - Components (全部组件)                │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│          Hooks                          │
│        ↓ imports                        │
│   - Utils                               │
│   - Types                               │
│   - Constants                           │
│   - API (from @/lib/api)                │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│     Utils / Types / Constants           │
│     (基础层，无内部依赖)                  │
└─────────────────────────────────────────┘
```

---

## 🎯 使用指南

### 如何添加新组件？

1. **确定组件类型**，选择对应的目录：
   - 画布相关 → `components/canvas/`
   - 节点相关 → `components/nodes/`
   - Mosaic 管理 → `components/mosaic/`
   - 其他功能 → 创建新的子目录

2. **创建组件文件**：`NewComponent.tsx`

3. **在 `index.ts` 中导出**：
   ```typescript
   export * from "./NewComponent"
   ```

4. **在使用的地方 import**：
   ```typescript
   import { NewComponent } from "../path/to/directory"
   ```

---

### 如何添加新的 Hook？

1. 在 `hooks/` 目录创建文件：`useNewFeature.ts`

2. 编写 Hook：
   ```typescript
   export function useNewFeature() {
     // Hook logic
     return { /* return values */ }
   }
   ```

3. 在 `hooks/index.ts` 中导出：
   ```typescript
   export * from "./useNewFeature"
   ```

4. 在组件中使用：
   ```typescript
   import { useNewFeature } from "../../hooks"

   function MyComponent() {
     const feature = useNewFeature()
     // use feature
   }
   ```

---

### 如何添加新的工具函数？

1. 确定功能类型：
   - 颜色相关 → `utils/colorHelpers.ts`
   - 节点相关 → `utils/nodeHelpers.ts`
   - 其他 → 创建新文件

2. 编写纯函数（无副作用）：
   ```typescript
   /**
    * Function description
    * @param param - Parameter description
    * @returns Return value description
    */
   export function myUtilFunction(param: Type): ReturnType {
     // Pure function logic
     return result
   }
   ```

3. 在 `utils/index.ts` 中导出

4. 在需要的地方 import 使用

---

### 如何添加新的类型？

1. 在 `types/canvas.types.ts` 中添加：
   ```typescript
   export interface NewType {
     // fields
   }
   ```

2. 类型会自动通过 `types/index.ts` 导出

3. 在需要的地方 import：
   ```typescript
   import type { NewType } from "../../types"
   ```

---

## 🔍 命名规范

### 文件命名
- **组件**: PascalCase，例如 `MosaicSidebar.tsx`
- **Hooks**: camelCase with `use` prefix，例如 `useMosaicManagement.ts`
- **工具函数**: camelCase，例如 `colorHelpers.ts`
- **类型**: camelCase with `.types` suffix，例如 `canvas.types.ts`
- **常量**: camelCase，例如 `mockData.ts`

### 代码命名
- **组件**: PascalCase，例如 `function MosaicSidebar()`
- **Hooks**: camelCase with `use` prefix，例如 `function useMosaicManagement()`
- **函数**: camelCase，例如 `function getEventTypeColor()`
- **常量**: UPPER_SNAKE_CASE，例如 `const NODE_TYPE_CONFIG`
- **变量**: camelCase，例如 `const currentMosaic`

### 注释规范
- **所有注释必须使用英文**
- **函数注释使用 JSDoc 格式**：
  ```typescript
  /**
   * Calculate incoming and outgoing connection counts for a node
   * @param nodeId - The ID of the node
   * @param connections - Array of connections
   * @returns Object with incoming/outgoing counts
   */
  export function getConnectionsForNode(...)
  ```

---

## 📈 重构成果

### 代码行数对比

| 项目 | 重构前 | 重构后 | 改善 |
|------|--------|--------|------|
| `page.tsx` | 1,874 行 | 17 行 | **-99%** |
| 文件数量 | 1 个 | 34 个 | +3,300% |
| 平均文件行数 | 1,874 行 | ~80 行 | **-95%** |

### 可维护性提升

- ✅ **模块化**: 每个文件职责单一
- ✅ **可测试**: Hooks 和工具函数可独立测试
- ✅ **可复用**: 组件和 Hooks 可在其他页面使用
- ✅ **可读性**: 清晰的文件结构和命名
- ✅ **团队协作**: 减少代码冲突，便于并行开发

---

## 🤝 维护指南

### 修改现有组件

1. 找到对应的组件文件
2. 修改组件代码
3. 如果修改了 Props，更新 TypeScript 接口
4. 测试功能是否正常

### 添加新功能

1. 确定功能属于哪个模块
2. 如果需要状态管理，先创建 Hook
3. 创建对应的 UI 组件
4. 在 `InfiniteCanvas.tsx` 中集成

### 重构建议

- **保持单一职责**: 每个文件只负责一个功能
- **避免循环依赖**: 遵循依赖层次关系
- **使用 TypeScript**: 充分利用类型检查
- **编写注释**: 使用英文注释说明复杂逻辑
- **保持一致性**: 遵循现有的命名和代码风格

---

## 📞 联系方式

如有问题或建议，请联系项目维护者。

---

## 📝 更新历史

### v1.3 (2026-01-22)
**画布连接和订阅管理功能 + 节点优化**
- ✨ 实现拖拽创建连接功能（ReactFlow Handle）
- 🔧 创建 `ConnectionConfigPanel.tsx` - 连接配置浮动面板
  - 选择会话对齐策略（Mirroring / Tasking / Agent-Driven）
  - 可选填写连接描述
  - 赛博朋克玻璃态风格 + 弹簧动画
- 🔧 创建 `EdgeContextMenu.tsx` - 连接线右键菜单
  - View Subscriptions（显示订阅数量）
  - Add Subscription
  - Edit Connection
  - Delete Connection
- 🔧 创建 `SubscriptionManagementPanel.tsx` - 订阅管理侧边栏
  - 从右侧滑入（480px 宽）
  - 13 种事件类型彩色徽章
  - 添加/编辑/删除订阅
- ✨ 节点连接点（Handle）
  - 每个节点 4 个连接点（上下左右）
  - 青色边框 + Hover 放大 1.5 倍
  - 支持拖拽创建连接
- ✨ AnimatedEdge 增强
  - 支持右键菜单（透明 hitbox）
  - 显示订阅数量徽章
  - Hover 时连接线变青色
  - 使用 EdgeLabelRenderer 渲染标签
- 🎨 节点卡片优化
  - 更新节点类型图标（Bot, Mail, Clock, Layers）
  - 移除 Messages 和 Activity 字段
  - 只保留 Active Sessions 显示（紧凑布局）
- 🗑️ 移除画布控制组件
  - 移除 Controls（缩放/锁定按钮）
  - 移除 MiniMap（右下角小地图）
  - 保留鼠标滚轮缩放和拖拽平移
- 🎯 InfiniteCanvas 状态管理
  - 新增 pendingConnection 状态
  - 新增 subscriptionPanelOpen 状态
  - 拦截 onConnect 事件触发配置面板

### v1.2 (2026-01-22)
**画布右键菜单功能 + 移除冗余组件 + 新增右上角快捷按钮**
- ✨ 新增画布空白处右键菜单功能
- 🔧 创建 `CanvasContextMenu.tsx` 组件，使用 Radix UI ContextMenu
- ✅ 右键点击画布空白处弹出自定义菜单（替代浏览器默认菜单）
- 🎯 菜单包含三个快捷操作：
  - Create Node - 创建新节点
  - Show Connections - 显示连接列表
  - Show/Hide Topology - 切换拓扑连接线显示
- 🎨 保持赛博朋克玻璃态风格（青色霓虹光效 + 半透明背景）
- ✅ 自动边界检测，确保菜单不会超出视口
- 🗑️ 移除 `LeftToolbar.tsx` 组件，功能整合到右键菜单
- 🗑️ 移除 `HUD.tsx` 顶部栏组件，功能整合到右键菜单
- ✨ 新增 `TopRightActions.tsx` 右上角快捷按钮组
  - Plus 按钮 - 快速创建节点
  - Command 按钮 - 打开命令面板（⌘K）
  - 悬停显示功能说明和快捷键提示
- 🎯 提升画布空间利用率，专注于节点展示
- 🎯 减少视觉干扰，保持界面简洁
- 🎨 视觉平衡：右上角按钮填补顶部空白区域

### v1.1 (2026-01-22)
**MosaicSidebar 交互优化**
- 🔧 使用 Radix UI ContextMenu 替代自定义右键菜单实现
- 🔧 使用 Radix UI Tooltip 替代自定义 hover tooltip
- ✅ 修复了右键菜单超出视口导致横向滚动条的问题
- ✅ 修复了 hover tooltip 导致纵向滚动条异常出现的问题
- ✅ 自动边界检测，确保菜单在任何屏幕尺寸下都不会超出视口
- 🎯 改进用户体验：直接右键点击即可调出菜单，无需额外操作
- 📦 新增依赖：`@radix-ui/react-context-menu` (2.2.16)

### v1.0 (2026-01-22)
**初始重构完成**
- 将 1874 行单文件拆分为 34 个模块化文件
- 建立清晰的依赖层次关系
- 实现 Mosaic 管理、节点管理、画布基础设施

---

**文档版本**: v1.3
**最后更新**: 2026-01-22
**维护者**: Mosaic Development Team
