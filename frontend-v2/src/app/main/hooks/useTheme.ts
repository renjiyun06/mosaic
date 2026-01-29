/**
 * useTheme Hook - Simplified Export
 *
 * Re-exports the useTheme hook from ThemeContext for cleaner imports.
 *
 * This file exists to provide a dedicated hooks directory structure
 * and cleaner import paths in components.
 *
 * Usage:
 * ```tsx
 * import { useTheme } from '@/app/main/hooks/useTheme'
 * // instead of
 * import { useTheme } from '@/app/main/contexts/ThemeContext'
 * ```
 *
 * @see /app/main/contexts/ThemeContext.tsx - Full implementation
 */

'use client'

export { useTheme } from '../contexts/ThemeContext'
