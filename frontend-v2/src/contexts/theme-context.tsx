"use client"

/**
 * Theme Context - Multi-theme switching system
 * Supports 5 themes: default, cyberpunk, glassmorphism, terminal, minimal
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

export type Theme = 'default' | 'cyberpunk' | 'glassmorphism' | 'terminal' | 'minimal'

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  themes: {
    id: Theme
    name: string
    description: string
    preview: string
  }[]
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

// Available themes configuration
const THEMES = [
  {
    id: 'default' as Theme,
    name: '默认主题',
    description: '企业蓝色，正式专业',
    preview: '#3B82F6',
  },
  {
    id: 'cyberpunk' as Theme,
    name: '赛博朋克',
    description: '霓虹发光，未来科技',
    preview: '#00FFFF',
  },
  {
    id: 'glassmorphism' as Theme,
    name: '玻璃态',
    description: '半透明模糊，现代高端',
    preview: 'linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05))',
  },
  {
    id: 'terminal' as Theme,
    name: '终端黑客',
    description: '纯黑绿字，Matrix 风格',
    preview: '#00FF41',
  },
  {
    id: 'minimal' as Theme,
    name: '极简主义',
    description: '纯净简洁，专注内容',
    preview: '#64748B',
  },
]

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('default')
  const [mounted, setMounted] = useState(false)

  // Initialize theme from localStorage
  useEffect(() => {
    setMounted(true)
    if (typeof window === 'undefined') return

    const savedTheme = localStorage.getItem('mosaic-theme') as Theme
    if (savedTheme && THEMES.some(t => t.id === savedTheme)) {
      setThemeState(savedTheme)
      document.documentElement.setAttribute('data-theme', savedTheme)
    } else {
      document.documentElement.setAttribute('data-theme', 'default')
    }
  }, [])

  // Update theme
  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)

    if (typeof window !== 'undefined') {
      localStorage.setItem('mosaic-theme', newTheme)
      document.documentElement.setAttribute('data-theme', newTheme)
    }
  }

  // Avoid hydration mismatch
  if (!mounted) {
    return <>{children}</>
  }

  const value: ThemeContextType = {
    theme,
    setTheme,
    themes: THEMES,
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
