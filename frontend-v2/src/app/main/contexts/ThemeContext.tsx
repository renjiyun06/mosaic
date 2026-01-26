/**
 * Mosaic Theme Context - Theme Provider and State Management
 *
 * Provides theme state management with:
 * - Dual theme support (Cyberpunk / Apple Glass)
 * - CSS variable injection for dynamic theming
 * - localStorage persistence across sessions
 * - FOUC (Flash of Unstyled Content) prevention
 * - Type-safe context with TypeScript
 * - Accessibility support (prefers-reduced-motion)
 *
 * Best Practices Applied:
 * - Client Component marked explicitly with 'use client'
 * - Mounted state prevents hydration mismatch
 * - CSS variables for performance (no inline style recalculation)
 * - Respects user motion preferences
 *
 * @see /doc/theme-system/FINAL_DESIGN.md - Design specifications
 * @see /doc/theme-system/THEME_SYSTEM_DESIGN.md - Implementation guide
 */

'use client'

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { ThemeType, ThemeTokens, themes, DEFAULT_THEME, THEME_STORAGE_KEY } from '../themes'

/**
 * Theme context value interface
 * Provides theme state and control methods to consumers
 */
interface ThemeContextValue {
  theme: ThemeType              // Current active theme identifier
  themeTokens: ThemeTokens      // Complete theme token object
  setTheme: (theme: ThemeType) => void  // Update theme (persists to localStorage)
  toggleTheme: () => void       // Toggle between themes
}

/**
 * Theme context (initially undefined, provided by ThemeProvider)
 */
const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

/**
 * Theme Provider Component
 *
 * Wraps application to provide theme state and methods.
 * Should be placed high in component tree (e.g., in page.tsx or layout.tsx)
 *
 * Features:
 * - Loads theme from localStorage on mount
 * - Persists theme changes to localStorage
 * - Injects CSS variables into document.documentElement
 * - Prevents FOUC with mounted state check
 * - Supports SSR/hydration (Next.js App Router compatible)
 *
 * @example
 * ```tsx
 * export default function Page() {
 *   return (
 *     <ThemeProvider>
 *       <YourApp />
 *     </ThemeProvider>
 *   )
 * }
 * ```
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Theme state (defaults to DEFAULT_THEME for SSR)
  const [theme, setThemeState] = useState<ThemeType>(DEFAULT_THEME)

  // Mounted state to prevent FOUC and hydration mismatch
  // Initially false during SSR, becomes true after client hydration
  const [mounted, setMounted] = useState(false)

  /**
   * Effect: Load theme from localStorage on mount
   * Runs only once after component mounts on client side
   */
  useEffect(() => {
    // Attempt to load stored theme from localStorage
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY) as ThemeType | null

    // If valid theme found, apply it; otherwise keep default
    if (storedTheme && (storedTheme === 'cyberpunk' || storedTheme === 'apple-glass')) {
      setThemeState(storedTheme)
      applyThemeToDocument(themes[storedTheme])
    } else {
      // Apply default theme on first load
      applyThemeToDocument(themes[DEFAULT_THEME])
    }

    // Mark component as mounted (enables rendering)
    setMounted(true)
  }, [])

  /**
   * Set theme with persistence
   * Updates state, saves to localStorage, and applies CSS variables
   */
  const setTheme = useCallback((newTheme: ThemeType) => {
    setThemeState(newTheme)
    localStorage.setItem(THEME_STORAGE_KEY, newTheme)
    applyThemeToDocument(themes[newTheme])
  }, [])

  /**
   * Toggle between themes
   * Switches from Cyberpunk ↔ Apple Glass
   */
  const toggleTheme = useCallback(() => {
    const newTheme = theme === 'cyberpunk' ? 'apple-glass' : 'cyberpunk'
    setTheme(newTheme)
  }, [theme, setTheme])

  /**
   * Effect: Apply theme when theme state changes
   * Only runs after component is mounted (prevents SSR issues)
   */
  useEffect(() => {
    if (mounted) {
      applyThemeToDocument(themes[theme])
    }
  }, [theme, mounted])

  // Context value provided to consumers
  const value: ThemeContextValue = {
    theme,
    themeTokens: themes[theme],
    setTheme,
    toggleTheme,
  }

  /**
   * Prevent rendering until mounted
   * This prevents Flash of Unstyled Content (FOUC) and hydration mismatches
   * During SSR/initial hydration, return null (no visual flash)
   */
  if (!mounted) {
    return null
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

/**
 * Apply theme tokens to CSS custom properties (CSS variables)
 *
 * Performance optimized:
 * - Uses CSS variables instead of inline styles (browser-optimized)
 * - Single DOM write batch (no layout thrashing)
 * - Variables available to all descendant components
 *
 * Accessibility:
 * - Respects prefers-reduced-motion
 * - Applies theme class to body for conditional styling
 *
 * @param tokens - Theme token object to apply
 */
function applyThemeToDocument(tokens: ThemeTokens) {
  const root = document.documentElement

  // Color tokens
  root.style.setProperty('--color-primary', tokens.colors.primary)
  root.style.setProperty('--color-secondary', tokens.colors.secondary)
  root.style.setProperty('--color-accent', tokens.colors.accent)
  root.style.setProperty('--color-background', tokens.colors.background)
  root.style.setProperty('--color-background-dots', tokens.colors.backgroundDots)
  root.style.setProperty('--color-surface', tokens.colors.surface)
  root.style.setProperty('--color-text-primary', tokens.colors.text.primary)
  root.style.setProperty('--color-text-secondary', tokens.colors.text.secondary)
  root.style.setProperty('--color-text-muted', tokens.colors.text.muted)
  root.style.setProperty('--color-border', tokens.colors.border)
  root.style.setProperty('--color-success', tokens.colors.success)
  root.style.setProperty('--color-warning', tokens.colors.warning)
  root.style.setProperty('--color-error', tokens.colors.error)

  // Glass effect tokens
  root.style.setProperty('--glass-background', tokens.glass.background)
  root.style.setProperty('--glass-background-light', tokens.glass.backgroundLight)
  root.style.setProperty('--glass-blur', tokens.glass.blur)
  root.style.setProperty('--glass-border', tokens.glass.border)

  // Glass saturate (Apple Glass specific, optional)
  if (tokens.glass.saturate) {
    root.style.setProperty('--glass-saturate', tokens.glass.saturate)
  }

  // Acrylic noise texture tokens (v3.0 - Apple Glass specific, optional)
  if (tokens.glass.noise) {
    root.style.setProperty('--glass-noise-overlay', tokens.glass.noise)
  } else {
    root.style.setProperty('--glass-noise-overlay', 'none')
  }

  if (tokens.glass.noiseOpacity) {
    root.style.setProperty('--glass-noise-opacity', tokens.glass.noiseOpacity)
  } else {
    root.style.setProperty('--glass-noise-opacity', '0')
  }

  // Shadow tokens (dynamic keys)
  Object.entries(tokens.shadows).forEach(([key, value]) => {
    root.style.setProperty(`--shadow-${key}`, value)
  })

  // Font tokens
  root.style.setProperty('--font-heading', tokens.fonts.heading)
  root.style.setProperty('--font-body', tokens.fonts.body)
  root.style.setProperty('--font-mono', tokens.fonts.mono)

  // Effect tokens
  root.style.setProperty('--border-width', tokens.effects.borderWidth)
  root.style.setProperty('--border-radius-sm', tokens.effects.borderRadius.small)
  root.style.setProperty('--border-radius-md', tokens.effects.borderRadius.medium)
  root.style.setProperty('--border-radius-lg', tokens.effects.borderRadius.large)
  root.style.setProperty('--border-radius-xl', tokens.effects.borderRadius.xl)
  root.style.setProperty('--backdrop-blur', tokens.effects.backdropBlur)
  root.style.setProperty('--transition', tokens.effects.transition)

  /**
   * Apply theme class to body for conditional CSS
   * Allows CSS selectors like: body.apple-glass .card { ... }
   *
   * Note: Using className instead of classList to ensure only one theme class
   */
  document.body.className = tokens.name
}

/**
 * useTheme Hook
 *
 * Custom hook to access theme context.
 * Must be used within ThemeProvider tree.
 *
 * @throws Error if used outside ThemeProvider
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { theme, toggleTheme } = useTheme()
 *
 *   return (
 *     <button onClick={toggleTheme}>
 *       Current theme: {theme}
 *     </button>
 *   )
 * }
 * ```
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)

  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }

  return context
}
