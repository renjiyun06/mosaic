# Mosaic 主题系统 - 快速开始指南

## 🎯 核心概念

### 双主题系统

```
Cyberpunk (现有)              Apple Glass (新增)
────────────────              ───────────────────
🌃 深色霓虹                    ☀️ 明亮玻璃
#00FFFF 青色                  #3B82F6 蓝色
赛博朋克风格                   苹果风格
适合夜间使用                   适合白天办公
```

---

## 📁 5 个核心文件

### 1️⃣ Design Tokens (`themes/tokens.ts`)

定义主题类型和接口。

### 2️⃣ Cyberpunk Theme (`themes/cyberpunk.ts`)

现有赛博朋克主题的 token 定义。

### 3️⃣ Apple Glass Theme (`themes/apple-glass.ts`)

新的苹果玻璃态主题 token 定义。

### 4️⃣ Theme Context (`contexts/ThemeContext.tsx`)

提供主题状态管理和 CSS 变量注入。

### 5️⃣ Theme Toggle (`components/shared/ThemeToggle.tsx`)

主题切换按钮组件。

---

## 🚀 快速实施 (3 步)

### Step 1: 创建主题文件

```bash
# 在 frontend-v2/src/app/main/ 目录下
mkdir -p themes contexts
```

复制以下文件到对应目录：
- `themes/tokens.ts`
- `themes/cyberpunk.ts`
- `themes/apple-glass.ts`
- `themes/index.ts`
- `contexts/ThemeContext.tsx`

### Step 2: 包裹 Theme Provider

**文件:** `page.tsx`

```tsx
import { ThemeProvider } from './contexts/ThemeContext'

export default function MainPage() {
  return (
    <ThemeProvider>
      <ReactFlowProvider>
        <InfiniteCanvas />
      </ReactFlowProvider>
    </ThemeProvider>
  )
}
```

### Step 3: 添加切换按钮

**文件:** `components/shared/ThemeToggle.tsx`

创建切换组件，然后在 `TopRightActions.tsx` 中引入：

```tsx
import { ThemeToggle } from '../shared/ThemeToggle'

export function TopRightActions({ ... }) {
  return (
    <div className="fixed top-6 right-6 flex items-center gap-3 z-50">
      <ThemeToggle />
      {/* 其他按钮 */}
    </div>
  )
}
```

---

## 🎨 组件迁移 - 快速参考

### 原则: 硬编码颜色 → CSS 变量

#### Before (硬编码):
```tsx
<div className="bg-slate-900/95 border border-cyan-400/20">
  <h1 className="text-cyan-400">Title</h1>
</div>
```

#### After (CSS 变量):
```tsx
<div
  style={{
    backgroundColor: 'var(--glass-background)',
    borderColor: 'var(--glass-border)',
  }}
>
  <h1 style={{ color: 'var(--color-primary)' }}>Title</h1>
</div>
```

### 快速替换表

| 原始 Tailwind Class | CSS 变量 |
|---------------------|----------|
| `border-cyan-400/20` | `var(--glass-border)` |
| `bg-slate-900/95` | `var(--glass-background)` |
| `text-cyan-400` | `var(--color-primary)` |
| `text-purple-400` | `var(--color-secondary)` |
| `shadow-[0_0_30px_rgba(34,211,238,0.3)]` | `var(--shadow-neon)` |

---

## 🔧 使用 Theme Hook

在任何组件中访问主题:

```tsx
import { useTheme } from '../../hooks/useTheme'

export function MyComponent() {
  const { theme, themeTokens, toggleTheme } = useTheme()

  return (
    <div>
      <p>Current theme: {theme}</p>
      <button onClick={toggleTheme}>Toggle Theme</button>
    </div>
  )
}
```

---

## 🎯 优先迁移顺序

### 第 1 批 (核心):
1. ✅ InfiniteCanvas (背景)
2. ✅ CollapsedNodeCard
3. ✅ ExpandedNodeCard

### 第 2 批 (侧边栏):
4. ✅ MosaicSidebar
5. ✅ ConnectionsSidebar
6. ✅ SubscriptionManagementPanel

### 第 3 批 (对话框):
7. ✅ MosaicDialog
8. ✅ CreateNodeCard
9. ✅ CreateConnectionDialog

### 第 4 批 (其他):
10. ✅ CommandPalette
11. ✅ TopRightActions
12. ✅ EdgeContextMenu

---

## ⚡ 性能优化提示

### ✅ DO (推荐):

```tsx
// 使用 CSS 变量
style={{ backgroundColor: 'var(--color-primary)' }}

// 使用 transform 和 opacity 做动画
transition={{ opacity: [0, 1], scale: [0.95, 1] }}
```

### ❌ DON'T (避免):

```tsx
// 避免动态计算
style={{ backgroundColor: theme === 'cyberpunk' ? '#00FFFF' : '#3B82F6' }}

// 避免使用 width/height 做动画
transition={{ width: [200, 400] }}
```

---

## 🧪 测试清单

完成迁移后，检查以下项目:

- [ ] 主题切换按钮可点击
- [ ] 切换后所有组件颜色正确
- [ ] 刷新页面主题保持不变 (localStorage)
- [ ] 动画流畅无闪烁
- [ ] 两个主题下文字都清晰可读
- [ ] 无控制台错误

---

## 🎨 主题视觉对比

### Cyberpunk Theme
```
背景: 深黑蓝 (#050510)
主色: 青色 (#00FFFF)
边框: 霓虹青色 + 发光效果
字体: Space Grotesk / DM Sans
效果: 强烈视觉冲击，科技感
```

### Apple Glass Theme
```
背景: 浅灰白 (#F8FAFC)
主色: 蓝色 (#3B82F6)
边框: 浅灰色 + 柔和阴影
字体: SF Pro / -apple-system
效果: 简洁优雅，专业感
```

---

## 📞 需要帮助?

查看完整文档: `THEME_SYSTEM_DESIGN.md`

**核心文件位置:**
```
frontend-v2/src/app/main/
├── themes/          # 主题 token 定义
├── contexts/        # Theme Provider
└── components/
    └── shared/
        └── ThemeToggle.tsx  # 切换按钮
```

---

**版本:** v1.0
**更新:** 2026-01-25
