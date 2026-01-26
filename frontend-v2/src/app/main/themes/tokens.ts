/**
 * Mosaic Theme System - Design Token Type Definitions
 *
 * Defines type-safe interfaces for dual theme system:
 * - Cyberpunk: Dark neon sci-fi (95% opacity, 20px blur)
 * - Apple Glass: Acrylic material glass (v3.0: 8% opacity, 8px blur, noise texture)
 *
 * @version 3.0 (2026-01-26) - Added Acrylic noise texture support
 * @see /doc/theme-system/ACRYLIC_ENHANCEMENT_V3.md - v3.0 specifications
 * @see /doc/theme-system/FINAL_DESIGN.md - v1.0 design parameters
 */

/**
 * Color token interface
 * Supports both solid colors and gradients
 */
export interface ColorTokens {
  primary: string        // Main brand color
  secondary: string      // Secondary brand color
  accent: string         // Call-to-action color
  background: string     // Page background (can be gradient)
  backgroundDots: string // ReactFlow background dots color
  surface: string        // Card/component surface
  text: {
    primary: string      // High-contrast body text
    secondary: string    // Medium-contrast secondary text
    muted: string        // Low-contrast muted text
  }
  border: string         // Default border color
  success: string        // Success state color
  warning: string        // Warning state color
  error: string          // Error state color
}

/**
 * Glass effect token interface
 * Supports both standard glassmorphism and Acrylic material (v3.0)
 */
export interface GlassTokens {
  background: string      // Glass background color with opacity
  backgroundLight: string // Lighter glass for hover/nested elements
  blur: string           // Backdrop blur amount (CSS value)
  border: string         // Glass border color with opacity
  saturate?: string      // Optional saturation boost (e.g., '110%')
  noise?: string         // Optional noise texture URL (v3.0: Acrylic material)
  noiseOpacity?: string  // Optional noise overlay opacity (v3.0: e.g., '0.05')
}

/**
 * Shadow token interface
 * Supports both neon glow and subtle glass shadows
 * Keys are dynamic to support different shadow types per theme
 */
export type ShadowTokens = Record<string, string>

/**
 * Font token interface
 * Defines font families for different text hierarchies
 */
export interface FontTokens {
  heading: string  // Font for headings (h1-h6)
  body: string     // Font for body text
  mono: string     // Font for code/monospace text
}

/**
 * Border radius token interface
 * Provides consistent corner radius across components
 */
export interface BorderRadiusTokens {
  small: string   // Small radius (e.g., 8px)
  medium: string  // Medium radius (e.g., 12px)
  large: string   // Large radius (e.g., 20px)
  xl: string      // Extra large radius (e.g., 24px)
}

/**
 * Effect token interface
 * Defines visual effects and transitions
 */
export interface EffectTokens {
  borderWidth: string              // Standard border width
  borderRadius: BorderRadiusTokens // Corner radius values
  backdropBlur: string             // Backdrop filter value (can include saturate)
  transition: string               // CSS transition timing
}

/**
 * Complete theme token interface
 * Combines all token types into a single theme definition
 */
export interface ThemeTokens {
  name: string           // Theme identifier (e.g., 'cyberpunk', 'apple-glass')
  colors: ColorTokens    // Color palette
  glass: GlassTokens     // Glass effect parameters
  shadows: ShadowTokens  // Shadow definitions
  fonts: FontTokens      // Typography settings
  effects: EffectTokens  // Visual effects and transitions
}

/**
 * Theme type union
 * Defines available theme identifiers
 */
export type ThemeType = 'cyberpunk' | 'apple-glass'

/**
 * Theme registry type
 * Maps theme identifiers to their token definitions
 */
export type ThemeRegistry = Record<ThemeType, ThemeTokens>
