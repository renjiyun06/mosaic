# Mosaic 主题切换系统 - 完整设计方案

> ⭐ **重要更新 (2026-01-25):**
> Apple Glass 主题参数已根据用户最终批准的 `demo-final.html` 修正：
> - 卡片不透明度: **3%** (原 70%)
> - 模糊度: **5px** (原 20px)
> - 边框: **0.5px solid rgba(255, 255, 255, 0.6)** (原 rgba(255, 255, 255, 0.2))
> - 这些是用户明确批准的最终参数，不可修改！

## 📋 执行摘要

为 Mosaic 项目设计双主题系统：
- **Cyberpunk Theme** (现有风格) - 深色霓虹赛博朋克
- **Apple Glass Theme** (新增风格) - 超薄超透明玻璃态

---

## 🎨 一、主题设计 Token 对比

### Theme 1: Cyberpunk (现有)

```typescript
const cyberpunkTheme = {
  name: 'cyberpunk',

  // Color Palette
  colors: {
    primary: '#00FFFF',        // Cyan neon
    secondary: '#7B61FF',      // Purple
    accent: '#FF00FF',         // Magenta
    background: '#050510',     // Deep dark blue
    surface: '#0F1419',        // Card background
    text: {
      primary: '#E0E0FF',      // Light lavender
      secondary: '#94A3B8',    // Muted gray
      muted: '#64748B',        // Darker muted
    },
    border: '#22d3ee',         // Cyan border (current)
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  },

  // Glass & Blur Effects
  glass: {
    background: 'rgba(15, 20, 25, 0.95)',
    backgroundLight: 'rgba(15, 20, 25, 0.85)',
    blur: '20px',
    border: 'rgba(34, 211, 238, 0.2)',
  },

  // Shadows & Glows
  shadows: {
    neon: '0 0 30px rgba(34, 211, 238, 0.3)',
    neonHover: '0 0 40px rgba(34, 211, 238, 0.5)',
    neonStrong: '0 0 50px rgba(34, 211, 238, 0.4)',
    card: '0 8px 32px rgba(0, 0, 0, 0.5)',
  },

  // Typography
  fonts: {
    heading: 'Space Grotesk, sans-serif',
    body: 'DM Sans, sans-serif',
    mono: 'Fira Code, monospace',
  },

  // Effects
  effects: {
    borderWidth: '1px',
    borderRadius: {
      small: '0.5rem',
      medium: '1rem',
      large: '1.5rem',
      xl: '2rem',
    },
    backdropBlur: 'blur(20px)',
    transition: '300ms ease-out',
  },
}
```

### Theme 2: Apple Glass (新增)

```typescript
const appleGlassTheme = {
  name: 'apple-glass',

  // Color Palette (明亮玻璃态 - 中性色系优化版)
  colors: {
    primary: '#0f172a',        // Slate 900 (neutral dark - main text/icons) ⭐
    secondary: '#1e293b',      // Slate 800 (secondary text) ⭐
    accent: '#3B82F6',         // Blue 500 (minimal accent for CTAs only) ⭐
    background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 40%, #e2e8f0 100%)', // ⭐ 明亮浅灰渐变（Slate 50-200）⭐
    backgroundDots: '#e2e8f0', // Slate 200 (ReactFlow dots)
    surface: 'rgba(255, 255, 255, 0.03)', // ⭐ 超透明卡片背景
    text: {
      primary: '#0f172a',      // Slate 900 (neutral, high contrast - 15.1:1) ⭐
      secondary: '#475569',    // Slate 600 (neutral secondary) ⭐
      muted: '#64748b',        // Slate 500 (neutral muted) ⭐
    },
    border: 'rgba(255, 255, 255, 0.6)', // ⭐ 60% opacity (visible but light)
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  },

  // Glass & Blur Effects (超薄超透明玻璃 - 用户批准的最终参数)
  glass: {
    background: 'rgba(255, 255, 255, 0.03)',      // ⭐ 3% 不透明（极度透明）
    backgroundLight: 'rgba(255, 255, 255, 0.05)', // ⭐ 5% 不透明（hover）
    blur: '5px',                                   // ⭐ 5px 模糊（轻微）
    border: 'rgba(255, 255, 255, 0.6)',           // ⭐ 60% 边框（超细）
    saturate: '105%',                              // ⭐ 饱和度增强
  },

  // Shadows (极简薄玻璃阴影 - 用户批准的最终参数)
  shadows: {
    glass: '0 4px 16px rgba(31, 38, 135, 0.08), 0 1px 4px rgba(31, 38, 135, 0.05)', // ⭐ 卡片基础阴影
    glassInset: 'inset 0 1px 0 rgba(255, 255, 255, 0.5)',                            // ⭐ 内部高光
    glassHover: '0 6px 24px rgba(31, 38, 135, 0.12), 0 2px 8px rgba(31, 38, 135, 0.08)', // ⭐ hover 阴影
    textScrim: '0 2px 8px rgba(0, 0, 0, 0.05)',                                      // ⭐ 文字背景阴影
    button: '0 2px 12px rgba(59, 130, 246, 0.2)',                                    // ⭐ 按钮阴影
  },

  // Typography (保持一致，或使用系统字体)
  fonts: {
    heading: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif',
    mono: '"SF Mono", "Fira Code", monospace',
  },

  // Effects
  effects: {
    borderWidth: '0.5px',      // ⭐ 超细边框
    borderRadius: {
      small: '0.5rem',         // ⭐ 8px
      medium: '0.75rem',       // ⭐ 12px
      large: '1.25rem',        // ⭐ 20px
      xl: '1.5rem',            // ⭐ 24px
    },
    backdropBlur: 'blur(5px) saturate(105%)', // ⭐ 轻微模糊 + 饱和度增强
    transition: '300ms cubic-bezier(0.4, 0, 0.2, 1)', // Smooth ease-out
  },
}
```

---

## 🏗️ 二、架构设计

### 文件结构

```
frontend-v2/
├── src/
│   ├── app/
│   │   └── main/
│   │       ├── contexts/
│   │       │   └── ThemeContext.tsx          # Theme Provider
│   │       ├── themes/
│   │       │   ├── tokens.ts                 # Design tokens
│   │       │   ├── cyberpunk.ts              # Cyberpunk theme
│   │       │   ├── apple-glass.ts            # Apple Glass theme
│   │       │   └── index.ts                  # Theme registry
│   │       ├── hooks/
│   │       │   └── useTheme.ts               # Theme hook
│   │       └── components/
│   │           └── shared/
│   │               └── ThemeToggle.tsx       # Toggle UI component
│   └── styles/
│       └── globals.css                       # CSS variables injection
```

---

## 🔧 三、核心实现

### 1. Design Tokens (`themes/tokens.ts`)

```typescript
/**
 * Design token type definitions
 */
export interface ThemeTokens {
  name: string
  colors: {
    primary: string
    secondary: string
    accent: string
    background: string
    surface: string
    text: {
      primary: string
      secondary: string
      muted: string
    }
    border: string
    success: string
    warning: string
    error: string
  }
  glass: {
    background: string
    backgroundLight: string
    blur: string
    border: string
  }
  shadows: Record<string, string>
  fonts: {
    heading: string
    body: string
    mono: string
  }
  effects: {
    borderWidth: string
    borderRadius: {
      small: string
      medium: string
      large: string
      xl: string
    }
    backdropBlur: string
    transition: string
  }
}

/**
 * Theme type union
 */
export type ThemeType = 'cyberpunk' | 'apple-glass'
```

### 2. Theme Definitions

**`themes/cyberpunk.ts`**
```typescript
import { ThemeTokens } from './tokens'

export const cyberpunkTheme: ThemeTokens = {
  name: 'cyberpunk',
  colors: {
    primary: '#00FFFF',
    secondary: '#7B61FF',
    accent: '#FF00FF',
    background: '#050510',
    surface: '#0F1419',
    text: {
      primary: '#E0E0FF',
      secondary: '#94A3B8',
      muted: '#64748B',
    },
    border: '#22d3ee',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  },
  glass: {
    background: 'rgba(15, 20, 25, 0.95)',
    backgroundLight: 'rgba(15, 20, 25, 0.85)',
    blur: '20px',
    border: 'rgba(34, 211, 238, 0.2)',
  },
  shadows: {
    neon: '0 0 30px rgba(34, 211, 238, 0.3)',
    neonHover: '0 0 40px rgba(34, 211, 238, 0.5)',
    neonStrong: '0 0 50px rgba(34, 211, 238, 0.4)',
    card: '0 8px 32px rgba(0, 0, 0, 0.5)',
  },
  fonts: {
    heading: 'Space Grotesk, sans-serif',
    body: 'DM Sans, sans-serif',
    mono: 'Fira Code, monospace',
  },
  effects: {
    borderWidth: '1px',
    borderRadius: {
      small: '0.5rem',
      medium: '1rem',
      large: '1.5rem',
      xl: '2rem',
    },
    backdropBlur: 'blur(20px)',
    transition: '300ms ease-out',
  },
}
```

**`themes/apple-glass.ts`** (优化版 - 中性色系)
```typescript
import { ThemeTokens } from './tokens'

export const appleGlassTheme: ThemeTokens = {
  name: 'apple-glass',
  colors: {
    primary: '#0f172a',        // Slate 900 (neutral dark) ⭐
    secondary: '#1e293b',      // Slate 800 (secondary) ⭐
    accent: '#3B82F6',         // Blue 500 (minimal accent only) ⭐
    background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 40%, #e2e8f0 100%)', // Bright Slate gradient ⭐
    backgroundDots: '#e2e8f0', // Slate 200 (ReactFlow dots)
    surface: 'rgba(255, 255, 255, 0.03)', // Ultra-transparent card
    text: {
      primary: '#0f172a',      // Slate 900 (neutral, 15.1:1 contrast) ⭐
      secondary: '#475569',    // Slate 600 (neutral) ⭐
      muted: '#64748b',        // Slate 500 (neutral) ⭐
    },
    border: 'rgba(255, 255, 255, 0.6)', // Light border (60%)
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  },
  glass: {
    background: 'rgba(255, 255, 255, 0.03)',      // ⭐ 3% opacity (ultra-thin)
    backgroundLight: 'rgba(255, 255, 255, 0.05)', // ⭐ 5% opacity (hover)
    blur: '5px',                                   // ⭐ 5px blur (light)
    border: 'rgba(255, 255, 255, 0.6)',           // ⭐ 60% border
    saturate: '105%',                              // ⭐ Saturation boost
  },
  shadows: {
    glass: '0 4px 16px rgba(31, 38, 135, 0.08), 0 1px 4px rgba(31, 38, 135, 0.05)',
    glassInset: 'inset 0 1px 0 rgba(255, 255, 255, 0.5)',
    glassHover: '0 6px 24px rgba(31, 38, 135, 0.12), 0 2px 8px rgba(31, 38, 135, 0.08)',
    textScrim: '0 2px 8px rgba(0, 0, 0, 0.05)',
    button: '0 2px 12px rgba(59, 130, 246, 0.2)',
  },
  fonts: {
    heading: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif',
    mono: '"SF Mono", "Fira Code", monospace',
  },
  effects: {
    borderWidth: '0.5px',      // Ultra-thin border
    borderRadius: {
      small: '0.5rem',         // 8px
      medium: '0.75rem',       // 12px
      large: '1.25rem',        // 20px
      xl: '1.5rem',            // 24px
    },
    backdropBlur: 'blur(5px) saturate(105%)', // Light blur + saturation
    transition: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },
}
```

**`themes/index.ts`**
```typescript
import { cyberpunkTheme } from './cyberpunk'
import { appleGlassTheme } from './apple-glass'
import { ThemeType, ThemeTokens } from './tokens'

export const themes: Record<ThemeType, ThemeTokens> = {
  cyberpunk: cyberpunkTheme,
  'apple-glass': appleGlassTheme,
}

export * from './tokens'
export { cyberpunkTheme, appleGlassTheme }
```

### 3. Theme Context (`contexts/ThemeContext.tsx`)

```typescript
'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import { ThemeType, ThemeTokens, themes } from '../themes'

interface ThemeContextValue {
  theme: ThemeType
  themeTokens: ThemeTokens
  setTheme: (theme: ThemeType) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

const THEME_STORAGE_KEY = 'mosaic-theme'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeType>('cyberpunk')
  const [mounted, setMounted] = useState(false)

  // Load theme from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as ThemeType | null
    if (stored && themes[stored]) {
      setThemeState(stored)
    }
    setMounted(true)
  }, [])

  // Persist theme to localStorage
  const setTheme = (newTheme: ThemeType) => {
    setThemeState(newTheme)
    localStorage.setItem(THEME_STORAGE_KEY, newTheme)
    applyThemeToDocument(themes[newTheme])
  }

  // Toggle between themes
  const toggleTheme = () => {
    const newTheme = theme === 'cyberpunk' ? 'apple-glass' : 'cyberpunk'
    setTheme(newTheme)
  }

  // Apply theme tokens to CSS variables
  useEffect(() => {
    if (mounted) {
      applyThemeToDocument(themes[theme])
    }
  }, [theme, mounted])

  const value: ThemeContextValue = {
    theme,
    themeTokens: themes[theme],
    setTheme,
    toggleTheme,
  }

  // Prevent flash of incorrect theme
  if (!mounted) {
    return null
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

/**
 * Apply theme tokens to CSS custom properties
 */
function applyThemeToDocument(tokens: ThemeTokens) {
  const root = document.documentElement

  // Colors
  root.style.setProperty('--color-primary', tokens.colors.primary)
  root.style.setProperty('--color-secondary', tokens.colors.secondary)
  root.style.setProperty('--color-accent', tokens.colors.accent)
  root.style.setProperty('--color-background', tokens.colors.background)
  root.style.setProperty('--color-surface', tokens.colors.surface)
  root.style.setProperty('--color-text-primary', tokens.colors.text.primary)
  root.style.setProperty('--color-text-secondary', tokens.colors.text.secondary)
  root.style.setProperty('--color-text-muted', tokens.colors.text.muted)
  root.style.setProperty('--color-border', tokens.colors.border)
  root.style.setProperty('--color-success', tokens.colors.success)
  root.style.setProperty('--color-warning', tokens.colors.warning)
  root.style.setProperty('--color-error', tokens.colors.error)

  // Glass
  root.style.setProperty('--glass-background', tokens.glass.background)
  root.style.setProperty('--glass-background-light', tokens.glass.backgroundLight)
  root.style.setProperty('--glass-blur', tokens.glass.blur)
  root.style.setProperty('--glass-border', tokens.glass.border)

  // Shadows
  Object.entries(tokens.shadows).forEach(([key, value]) => {
    root.style.setProperty(`--shadow-${key}`, value)
  })

  // Fonts
  root.style.setProperty('--font-heading', tokens.fonts.heading)
  root.style.setProperty('--font-body', tokens.fonts.body)
  root.style.setProperty('--font-mono', tokens.fonts.mono)

  // Effects
  root.style.setProperty('--border-width', tokens.effects.borderWidth)
  root.style.setProperty('--border-radius-sm', tokens.effects.borderRadius.small)
  root.style.setProperty('--border-radius-md', tokens.effects.borderRadius.medium)
  root.style.setProperty('--border-radius-lg', tokens.effects.borderRadius.large)
  root.style.setProperty('--border-radius-xl', tokens.effects.borderRadius.xl)
  root.style.setProperty('--backdrop-blur', tokens.effects.backdropBlur)
  root.style.setProperty('--transition', tokens.effects.transition)

  // Add theme class to body for conditional styling
  document.body.className = tokens.name
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}
```

### 4. Theme Hook (`hooks/useTheme.ts`)

```typescript
'use client'

import { useContext } from 'react'
import { ThemeContext } from '../contexts/ThemeContext'

export { useTheme } from '../contexts/ThemeContext'
```

### 5. Theme Toggle Component (`components/shared/ThemeToggle.tsx`)

```typescript
'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../../hooks/useTheme'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

  return (
    <motion.button
      onClick={toggleTheme}
      className="relative w-16 h-8 rounded-full flex items-center transition-colors duration-300"
      style={{
        backgroundColor: isAppleGlass
          ? 'var(--color-border)'
          : 'rgba(34, 211, 238, 0.2)',
      }}
      whileTap={{ scale: 0.95 }}
      aria-label={`Switch to ${isAppleGlass ? 'Cyberpunk' : 'Apple Glass'} theme`}
    >
      {/* Toggle Circle */}
      <motion.div
        className="absolute w-6 h-6 rounded-full flex items-center justify-center"
        style={{
          backgroundColor: isAppleGlass ? '#3B82F6' : '#00FFFF',
          boxShadow: isAppleGlass
            ? '0 2px 8px rgba(59, 130, 246, 0.3)'
            : '0 0 20px rgba(0, 255, 255, 0.5)',
        }}
        initial={false}
        animate={{
          x: isAppleGlass ? 32 : 4,
        }}
        transition={{
          type: 'spring',
          stiffness: 500,
          damping: 30,
        }}
      >
        {isAppleGlass ? (
          <Sun className="w-4 h-4 text-white" />
        ) : (
          <Moon className="w-4 h-4 text-slate-900" />
        )}
      </motion.div>

      {/* Background Icons */}
      <div className="absolute inset-0 flex items-center justify-between px-2 pointer-events-none">
        <Moon
          className="w-4 h-4 transition-opacity duration-300"
          style={{
            color: isAppleGlass ? '#94A3B8' : '#00FFFF',
            opacity: isAppleGlass ? 0.5 : 0,
          }}
        />
        <Sun
          className="w-4 h-4 transition-opacity duration-300"
          style={{
            color: isAppleGlass ? '#3B82F6' : '#64748B',
            opacity: isAppleGlass ? 0 : 0.5,
          }}
        />
      </div>
    </motion.button>
  )
}
```

### 6. Update `globals.css`

```css
/* CSS Variables will be injected by ThemeContext */
:root {
  /* Colors */
  --color-primary: #00FFFF;
  --color-secondary: #7B61FF;
  --color-accent: #FF00FF;
  --color-background: #050510;
  --color-surface: #0F1419;
  --color-text-primary: #E0E0FF;
  --color-text-secondary: #94A3B8;
  --color-text-muted: #64748B;
  --color-border: #22d3ee;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;

  /* Glass */
  --glass-background: rgba(15, 20, 25, 0.95);
  --glass-background-light: rgba(15, 20, 25, 0.85);
  --glass-blur: 20px;
  --glass-border: rgba(34, 211, 238, 0.2);

  /* Shadows */
  --shadow-neon: 0 0 30px rgba(34, 211, 238, 0.3);
  --shadow-neonHover: 0 0 40px rgba(34, 211, 238, 0.5);
  --shadow-neonStrong: 0 0 50px rgba(34, 211, 238, 0.4);
  --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.5);

  /* Fonts */
  --font-heading: 'Space Grotesk', sans-serif;
  --font-body: 'DM Sans', sans-serif;
  --font-mono: 'Fira Code', monospace;

  /* Effects */
  --border-width: 1px;
  --border-radius-sm: 0.5rem;
  --border-radius-md: 1rem;
  --border-radius-lg: 1.5rem;
  --border-radius-xl: 2rem;
  --backdrop-blur: blur(20px);
  --transition: 300ms ease-out;
}

/* Smooth color transitions on theme change */
* {
  transition: background-color var(--transition),
              border-color var(--transition),
              color var(--transition);
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
    animation: none !important;
  }
}

/* Body background */
body {
  background-color: var(--color-background);
  color: var(--color-text-primary);
  font-family: var(--font-body);
}
```

---

## 🎯 四、组件迁移指南

### 原有组件样式迁移策略

**硬编码颜色 → CSS 变量**

#### Before:
```tsx
<div className="bg-slate-900/95 border border-cyan-400/20">
```

#### After:
```tsx
<div
  style={{
    backgroundColor: 'var(--glass-background)',
    borderColor: 'var(--glass-border)',
  }}
>
```

### 常用替换映射表

| 原始 Tailwind | CSS 变量 | 说明 |
|--------------|----------|------|
| `border-cyan-400/20` | `var(--glass-border)` | 玻璃边框 |
| `bg-slate-900/95` | `var(--glass-background)` | 玻璃背景 |
| `text-cyan-400` | `var(--color-primary)` | 主色文字 |
| `shadow-[0_0_30px_rgba(34,211,238,0.3)]` | `var(--shadow-neon)` | 霓虹阴影 |
| `rounded-3xl` | `var(--border-radius-xl)` | 大圆角 |

### 渐进式迁移

**阶段 1: 核心组件**
- InfiniteCanvas
- NodeCards (Collapsed & Expanded)
- MosaicSidebar

**阶段 2: 对话框和面板**
- MosaicDialog
- CreateNodeCard
- ConnectionsSidebar

**阶段 3: 其他组件**
- CommandPalette
- TopRightActions
- CanvasContextMenu

---

## 🚀 五、实施步骤

### Step 1: 创建主题基础设施 (第 1 天)

1. 创建 `themes/` 目录和所有 token 文件
2. 实现 `ThemeContext.tsx`
3. 创建 `useTheme` hook
4. 更新 `globals.css`

### Step 2: 集成 Theme Provider (第 1 天)

在 `page.tsx` 中包裹 ThemeProvider:

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

### Step 3: 添加主题切换按钮 (第 2 天)

在 `TopRightActions.tsx` 中添加 ThemeToggle:

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

### Step 4: 迁移核心组件 (第 3-5 天)

**优先级顺序:**
1. InfiniteCanvas (背景)
2. CollapsedNodeCard
3. ExpandedNodeCard
4. MosaicSidebar
5. 其余组件

**迁移模板:**

```tsx
// Before
<div className="bg-slate-900/95 backdrop-blur-xl border border-cyan-400/20">

// After
<div
  style={{
    backgroundColor: 'var(--glass-background)',
    backdropFilter: 'var(--backdrop-blur)',
    borderColor: 'var(--glass-border)',
  }}
>
```

### Step 5: 测试和优化 (第 6 天)

- [ ] 测试主题切换动画流畅度
- [ ] 检查所有组件在两个主题下的显示效果
- [ ] 验证 localStorage 持久化
- [ ] 测试无障碍性 (prefers-reduced-motion)
- [ ] 性能测试 (主题切换是否卡顿)

---

## 📐 六、设计规范对比

### Cyberpunk Theme 使用场景

✅ **适合:**
- 技术感强烈的仪表盘
- 夜间使用场景
- 强调视觉冲击力
- 科技/游戏风格产品

❌ **不适合:**
- 长时间阅读
- 专业商务场景
- 打印或分享

### Apple Glass Theme 使用场景

✅ **适合:**
- 白天办公环境
- 长时间工作
- 专业演示场景
- 需要打印或截图分享
- 追求简洁现代感

❌ **不适合:**
- 夜间低光环境
- 追求强烈视觉冲击

---

## ♿ 七、无障碍性考虑

### 1. 颜色对比度

**Cyberpunk:**
- 文字: `#E0E0FF` on `#050510` = **14.2:1** ✅ (AAA 级别)
- 边框: `#22d3ee` on `#050510` = **6.8:1** ✅ (AA 级别)

**Apple Glass:**
- 文字: `#0F172A` on `#F8FAFC` = **15.1:1** ✅ (AAA 级别)
- 边框: `#E2E8F0` on `#FFFFFF` = **1.2:1** ⚠️ (需要增强)

**修正方案:**
```typescript
// apple-glass.ts
border: '#CBD5E1', // Slate 300 (更深)
```

### 2. Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
    animation: none !important;
  }
}
```

### 3. Focus States

确保焦点环在两个主题下都清晰可见:

```tsx
className="focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
```

---

## 🎬 八、动画和过渡

### 主题切换动画策略

**使用 Framer Motion 的 AnimatePresence**

```tsx
import { AnimatePresence, motion } from 'framer-motion'

<AnimatePresence mode="wait">
  <motion.div
    key={theme}
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    transition={{ duration: 0.3 }}
  >
    {/* Content */}
  </motion.div>
</AnimatePresence>
```

### 推荐动画时长

- **颜色过渡:** 300ms ease-out
- **背景模糊:** 300ms ease-out
- **阴影变化:** 300ms ease-out
- **布局变化:** 避免 (保持一致)

---

## 📊 九、性能优化

### 1. CSS Variables vs. Inline Styles

✅ **推荐:** CSS Variables (更快)
```tsx
style={{ backgroundColor: 'var(--color-primary)' }}
```

❌ **避免:** 动态计算
```tsx
style={{ backgroundColor: theme === 'cyberpunk' ? '#00FFFF' : '#3B82F6' }}
```

### 2. 延迟加载字体

```tsx
// app/layout.tsx
import { Space_Grotesk, DM_Sans, Fira_Code } from 'next/font/google'

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-heading'
})
```

### 3. 避免重排 (Reflow)

使用 `transform` 和 `opacity` 而非 `width/height`:

```tsx
// ✅ Good
transition={{ opacity: [0, 1], scale: [0.95, 1] }}

// ❌ Bad
transition={{ width: [200, 400] }}
```

---

## 🧪 十、测试清单

### 功能测试

- [ ] 主题切换按钮工作正常
- [ ] 主题持久化到 localStorage
- [ ] 刷新页面后主题保持
- [ ] 所有组件在两个主题下正常显示

### 视觉测试

- [ ] Cyberpunk: 霓虹效果清晰可见
- [ ] Apple Glass: 玻璃态效果自然
- [ ] 过渡动画流畅 (无闪烁)
- [ ] 文字在两个主题下都清晰可读

### 性能测试

- [ ] 主题切换 < 300ms
- [ ] 无明显卡顿或延迟
- [ ] 内存占用正常

### 无障碍测试

- [ ] 键盘可访问主题切换按钮
- [ ] prefers-reduced-motion 生效
- [ ] 颜色对比度符合 WCAG AA 标准
- [ ] 焦点状态清晰可见

---

## 📚 十一、参考资源

### Design Systems

- **Apple HIG:** https://developer.apple.com/design/human-interface-guidelines/
- **Glassmorphism:** https://uxdesign.cc/glassmorphism-in-user-interfaces-1f39bb1308c9
- **Cyberpunk UI:** https://www.cyberpunk.net/

### Code Examples

- **next-themes:** https://github.com/pacocoursey/next-themes
- **Radix UI Themes:** https://www.radix-ui.com/themes/docs/overview/getting-started
- **Tailwind Dark Mode:** https://tailwindcss.com/docs/dark-mode

---

## 🎉 完成标准

项目完成时应达到:

1. ✅ 两个主题完全实现，视觉效果符合设计规范
2. ✅ 主题切换流畅，无视觉故障
3. ✅ 所有现有组件已迁移到 CSS 变量系统
4. ✅ 主题选择持久化到 localStorage
5. ✅ 通过无障碍性测试 (WCAG AA)
6. ✅ 通过性能测试 (切换 < 300ms)
7. ✅ 文档完整，包含使用指南

---

**文档版本:** v1.1 (优化版 - 中性色系)
**创建日期:** 2026-01-25
**更新日期:** 2026-01-25
**作者:** Mosaic Development Team
**状态:** 设计完成，已实施部分组件
**优化内容:**
- 背景更明亮（Slate 50→100→200）
- 主色改为中性深灰（Slate 900/800）
- 文字颜色改为中性 Slate 系列
- 移除蓝色主色，采用 VisionOS-inspired 中性美学
