/**
 * Mosaic Theme System - Central Export
 *
 * Exports all themes, types, and helper utilities for the dual theme system.
 *
 * Usage:
 * ```tsx
 * import { themes, ThemeType, ThemeTokens } from './themes'
 *
 * const currentTheme = themes['cyberpunk']
 * ```
 */

import { cyberpunkTheme } from './cyberpunk'
import { appleGlassTheme, textScrimTokens, backgroundContrastTokens } from './apple-glass'
import type {
  ThemeTokens,
  ThemeType,
  ThemeRegistry,
  ColorTokens,
  GlassTokens,
  ShadowTokens,
  FontTokens,
  EffectTokens,
  BorderRadiusTokens,
} from './tokens'

/**
 * Theme registry
 * Maps theme identifiers to their complete token definitions
 */
export const themes: ThemeRegistry = {
  cyberpunk: cyberpunkTheme,
  'apple-glass': appleGlassTheme,
}

/**
 * Default theme identifier
 * Used when no theme is specified or stored theme is invalid
 */
export const DEFAULT_THEME: ThemeType = 'cyberpunk'

/**
 * Theme storage key for localStorage
 * Used to persist user's theme preference across sessions
 */
export const THEME_STORAGE_KEY = 'mosaic-theme'

/**
 * Helper: Get theme tokens by name
 * Returns theme tokens or default theme if name is invalid
 */
export function getThemeTokens(themeName: ThemeType): ThemeTokens {
  return themes[themeName] || themes[DEFAULT_THEME]
}

/**
 * Helper: Check if theme name is valid
 */
export function isValidTheme(themeName: string): themeName is ThemeType {
  return themeName === 'cyberpunk' || themeName === 'apple-glass'
}

/**
 * Helper: Get next theme in rotation
 * Used for theme toggle functionality
 */
export function getNextTheme(currentTheme: ThemeType): ThemeType {
  return currentTheme === 'cyberpunk' ? 'apple-glass' : 'cyberpunk'
}

// Re-export all types for convenient importing
export type {
  ThemeTokens,
  ThemeType,
  ThemeRegistry,
  ColorTokens,
  GlassTokens,
  ShadowTokens,
  FontTokens,
  EffectTokens,
  BorderRadiusTokens,
}

// Re-export individual themes
export { cyberpunkTheme, appleGlassTheme }

// Re-export Apple Glass specific tokens
export { textScrimTokens, backgroundContrastTokens }
