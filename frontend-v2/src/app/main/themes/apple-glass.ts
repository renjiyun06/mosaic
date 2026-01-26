/**
 * Mosaic Theme - Apple Glass
 *
 * Ultra-thin transparent glass theme with Acrylic material enhancement
 * ⭐ USER-APPROVED v3.0 PARAMETERS (from demo-acrylic-enhanced.html)
 *
 * - Card opacity: 8% Acrylic material (enhanced from 3% v2.0)
 * - Blur: 8px with 110% saturation (enhanced from 5px v2.0)
 * - Border: 1px solid rgba(255, 255, 255, 0.7) (enhanced from 0.5px v2.0)
 * - Noise texture: SVG fractal noise @ 5% opacity (NEW - Acrylic depth)
 * - Shadows: Soft subtle (no glow)
 * - Background: v2.0 enhanced contrast blocks (6 layers)
 * - Text: Each element has own semi-transparent scrim (15.1:1 contrast)
 *
 * Best for: Daytime use, professional presentations, clean aesthetic
 *
 * CRITICAL: Do NOT modify opacity or blur values without user approval!
 *
 * @version 3.0 (2026-01-26) - Acrylic Material Enhancement
 * @see /doc/theme-system/demo-acrylic-enhanced.html - User-approved v3.0 demo
 * @see /doc/theme-system/ACRYLIC_ENHANCEMENT_V3.md - v3.0 technical specification
 * @see /doc/theme-system/FINAL_DESIGN.md - v1.0 design specification
 */

import { ThemeTokens } from './tokens'

/**
 * SVG Noise Texture for Acrylic Material (v3.0)
 *
 * Base64-encoded SVG fractal noise pattern for subtle material depth.
 * Applied at 5% opacity as background overlay to create Acrylic glass effect.
 *
 * Inspiration: Apple VisionOS + Microsoft Fluent Design Acrylic material
 *
 * Performance: Minimal impact (inline base64, no network request, ~500 bytes)
 */
const ACRYLIC_NOISE_TEXTURE = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzMDAiIGhlaWdodD0iMzAwIj48ZmlsdGVyIGlkPSJhIj48ZmVUdXJidWxlbmNlIGJhc2VGcmVxdWVuY3k9Ii43NSIgc3RpdGNoVGlsZXM9InN0aXRjaCIgdHlwZT0iZnJhY3RhbE5vaXNlIi8+PGZlQ29sb3JNYXRyaXggdHlwZT0ic2F0dXJhdGUiIHZhbHVlcz0iMCIvPjwvZmlsdGVyPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbHRlcj0idXJsKCNhKSIgb3BhY2l0eT0iMC4wNSIvPjwvc3ZnPg=='

/**
 * Background Contrast Block Type Definition
 * Used for dark and light blocks in Apple Glass background
 */
interface ContrastBlock {
  gradient: string
  opacity: number
  size: string
  position: { top?: string; bottom?: string; left?: string; right?: string }
  rotation: string
  borderRadius?: string
  boxShadow?: string
}

/**
 * Decorative Line Type Definition
 * Used for horizontal and vertical lines in Apple Glass background
 */
interface DecorativeLine {
  type: 'horizontal' | 'vertical'
  gradient: string
  opacity: number
  width?: string
  height?: string
  position: { top?: string; bottom?: string; left?: string; right?: string }
}

/**
 * Accent Dot Type Definition (v2.0)
 * Colorful visual anchors for transparency effect
 */
interface AccentDot {
  color: string
  size: string
  blur: string
  position: { top?: string; bottom?: string; left?: string; right?: string }
}

/**
 * Background Contrast Tokens Type Definition
 * Complete type for Apple Glass background system
 */
interface BackgroundContrastTokens {
  baseGradient: string
  radialOverlays: string[]
  darkBlocks: ContrastBlock[]
  lightBlocks: ContrastBlock[]
  lines: DecorativeLine[]
  accentDots?: AccentDot[]
}

export const appleGlassTheme: ThemeTokens = {
  name: 'apple-glass',

  // Color Palette - Neutral and Elegant (VisionOS-inspired)
  colors: {
    primary: '#0f172a',        // Slate-900 (neutral dark - main text/icons)
    secondary: '#1e293b',      // Slate-800 (secondary text)
    accent: '#3B82F6',         // Blue-500 (minimal accent for important CTAs only)
    // ⭐ CRITICAL: Brighter background gradient for better visibility
    background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 40%, #e2e8f0 100%)', // Slate 50→100→200 (brighter!)
    backgroundDots: '#e2e8f0', // Slate-200 for ReactFlow dots (subtle on bright background)
    surface: 'rgba(255, 255, 255, 0.03)', // ⭐ 3% opacity (ultra-transparent card)
    text: {
      primary: '#0f172a',      // Slate-900 (neutral, high contrast - 15.1:1)
      secondary: '#475569',    // Slate-600 (neutral secondary)
      muted: '#64748b',        // Slate-500 (neutral muted)
    },
    border: 'rgba(255, 255, 255, 0.6)', // ⭐ 60% opacity (visible but light)
    success: '#10b981',        // Emerald-500
    warning: '#f59e0b',        // Amber-500
    error: '#ef4444',          // Red-500
  },

  // Glass & Blur Effects - Acrylic Material Enhancement (v3.0)
  // ⭐ CRITICAL: These are user-approved v3.0 values, do NOT change!
  // Enhanced from v2.0 to reduce visual noise while maintaining transparency
  glass: {
    background: 'rgba(255, 255, 255, 0.08)',      // ⭐ 8% opacity (v3.0: enhanced from 3%)
    backgroundLight: 'rgba(255, 255, 255, 0.10)', // ⭐ 10% opacity (v3.0: hover state enhanced)
    blur: '8px',                                   // ⭐ 8px blur (v3.0: enhanced from 5px)
    border: 'rgba(255, 255, 255, 0.7)',           // ⭐ 70% border (v3.0: enhanced from 60%)
    saturate: '110%',                              // ⭐ 110% saturation (v3.0: enhanced from 105%)
    noise: `url("${ACRYLIC_NOISE_TEXTURE}")`,     // ⭐ v3.0 NEW: Acrylic noise texture
    noiseOpacity: '0.05',                          // ⭐ v3.0 NEW: 5% noise overlay opacity
  },

  // Shadows - Soft Subtle Glass Effects
  // ⭐ These shadow values create the thin glass appearance
  shadows: {
    // Card shadows - minimal and soft
    glass: '0 4px 16px rgba(31, 38, 135, 0.08), 0 1px 4px rgba(31, 38, 135, 0.05)',
    glassInset: 'inset 0 1px 0 rgba(255, 255, 255, 0.5)',   // Top highlight
    glassHover: '0 6px 24px rgba(31, 38, 135, 0.12), 0 2px 8px rgba(31, 38, 135, 0.08)',

    // Text scrim shadows - ensures readability on transparent cards
    textScrim: '0 2px 8px rgba(0, 0, 0, 0.05)',

    // Button shadow
    button: '0 2px 12px rgba(59, 130, 246, 0.2)',
  },

  // Typography - Apple System Fonts
  fonts: {
    heading: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif',
    mono: '"SF Mono", "Fira Code", monospace',
  },

  // Effects - Smooth and Refined (v3.0 Acrylic Enhancement)
  effects: {
    borderWidth: '1px',                             // ⭐ v3.0: Enhanced from 0.5px
    borderRadius: {
      small: '0.5rem',                              // 8px (slightly smaller)
      medium: '0.75rem',                            // 12px (card default)
      large: '1.25rem',                             // 20px (large cards)
      xl: '1.5rem',                                 // 24px (extra large)
    },
    backdropBlur: 'blur(8px) saturate(110%)',      // ⭐ v3.0: Enhanced blur + saturation
    transition: '300ms cubic-bezier(0.4, 0, 0.2, 1)', // Smooth ease-out
  },
}

/**
 * Text Scrim Parameters (for component implementation)
 *
 * Each text element should have its own semi-transparent background
 * to ensure readability on ultra-transparent cards.
 *
 * Usage in components:
 * - Title: background: rgba(255, 255, 255, 0.5), backdrop-filter: blur(8px)
 * - Subtitle: background: rgba(255, 255, 255, 0.45), backdrop-filter: blur(8px)
 * - Content: background: rgba(255, 255, 255, 0.5), backdrop-filter: blur(8px)
 * - Nested elements: background: rgba(255, 255, 255, 0.4), backdrop-filter: blur(8px)
 *
 * All text scrims should include:
 * - border: 0.5px solid rgba(255, 255, 255, 0.25-0.35)
 * - border-radius: 8-12px
 * - padding: appropriate for element type
 */
export const textScrimTokens = {
  title: {
    background: 'rgba(255, 255, 255, 0.5)',
    backdropFilter: 'blur(8px)',
    border: '0.5px solid rgba(255, 255, 255, 0.3)',
    borderRadius: '10px',
    padding: '6px 10px',
  },
  subtitle: {
    background: 'rgba(255, 255, 255, 0.45)',
    backdropFilter: 'blur(8px)',
    border: '0.5px solid rgba(255, 255, 255, 0.25)',
    borderRadius: '8px',
    padding: '5px 10px',
  },
  content: {
    background: 'rgba(255, 255, 255, 0.5)',
    backdropFilter: 'blur(8px)',
    border: '0.5px solid rgba(255, 255, 255, 0.3)',
    borderRadius: '12px',
    padding: '14px',
  },
  nested: {
    background: 'rgba(255, 255, 255, 0.4)',
    backdropFilter: 'blur(8px)',
    border: '0.5px solid rgba(255, 255, 255, 0.35)',
    borderRadius: '12px',
    padding: '12px 16px',
  },
}

/**
 * Background Contrast Blocks Parameters (for InfiniteCanvas implementation)
 *
 * ENHANCED CONTRAST VERSION (v2.0) - Based on VisionOS Spatial UI & Glassmorphism best practices
 *
 * The Apple Glass theme requires STRONG dark/light contrast blocks to make
 * ultra-transparent 3% opacity cards show visible see-through effect.
 *
 * Key improvements over v1.0:
 * - 75% stronger dark blocks (Slate-800/900 instead of 300/200)
 * - 100% opaque light blocks with shadows
 * - Colorful accent dots (Indigo/Pink) for visual interest
 * - Sharper boundaries (border-radius) for clarity
 * - Enhanced line opacity for depth
 *
 * Usage in InfiniteCanvas:
 * - 5 layers: base gradient → radial overlays → dark blocks → light blocks → lines → accent dots
 */
export const backgroundContrastTokens: BackgroundContrastTokens = {
  // Layer 1: Base gradient with cold/warm contrast (Indigo → Slate → Pink)
  baseGradient: 'linear-gradient(135deg, #e0e7ff 0%, #f1f5f9 50%, #fce7f3 100%)',
  // Indigo-100 → Slate-100 → Pink-100 (adds color interest while staying bright)

  // Layer 2: Radial color halos (visual interest points)
  radialOverlays: [
    'radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.12) 0%, transparent 50%)', // Indigo-500 top-left
    'radial-gradient(circle at 80% 70%, rgba(236, 72, 153, 0.10) 0%, transparent 50%)', // Pink-500 bottom-right
  ],

  // Layer 3: STRONG dark contrast blocks (Slate-800/900 - much deeper than before!)
  darkBlocks: [
    {
      gradient: 'linear-gradient(135deg, #1e293b, #334155)', // Slate-800 → Slate-700
      opacity: 0.7, // ⬆️ Increased from 0.4 (75% stronger!)
      size: '400px', // ⬆️ Larger for more impact
      position: { top: '8%', left: '-80px' },
      rotation: '-12deg',
      borderRadius: '24px', // ⭐ Sharper boundaries for clarity
      boxShadow: '0 8px 24px rgba(15, 23, 42, 0.15)', // ⭐ Subtle shadow for depth
    },
    {
      gradient: 'linear-gradient(45deg, #0f172a, #1e293b)', // Slate-900 → Slate-800
      opacity: 0.65, // ⬆️ Increased from 0.35 (86% stronger!)
      size: '320px',
      position: { bottom: '12%', right: '-60px' },
      rotation: '18deg',
      borderRadius: '20px',
      boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
    },
  ],

  // Layer 4: BRIGHT light blocks with maximum opacity + shadows
  lightBlocks: [
    {
      gradient: 'linear-gradient(135deg, #ffffff, #f5f5ff)', // Pure white → Indigo-tint
      opacity: 1.0, // ⬆️ 100% opaque (maximum contrast)
      size: '280px', // ⬆️ Larger
      position: { top: '45%', right: '12%' },
      rotation: '8deg',
      borderRadius: '28px',
      boxShadow: '0 8px 32px rgba(99, 102, 241, 0.08)', // ⭐ Indigo shadow
    },
    {
      gradient: 'linear-gradient(45deg, #ffffff, #fff5f7)', // Pure white → Pink-tint
      opacity: 0.95, // ⬆️ Nearly opaque
      size: '220px',
      position: { bottom: '28%', left: '8%' },
      rotation: '-8deg',
      borderRadius: '24px',
      boxShadow: '0 8px 32px rgba(236, 72, 153, 0.06)', // ⭐ Pink shadow
    },
  ],

  // Layer 5: Enhanced decorative lines (stronger visibility)
  lines: [
    {
      type: 'horizontal',
      gradient: 'linear-gradient(90deg, transparent, rgba(30, 41, 59, 0.5), transparent)', // Slate-800
      opacity: 0.35, // ⬆️ Increased from 0.2 (75% stronger)
      width: '500px',
      height: '3px',
      position: { top: '25%', right: '0' },
    },
    {
      type: 'vertical',
      gradient: 'linear-gradient(180deg, transparent, rgba(51, 65, 85, 0.45), transparent)', // Slate-700
      opacity: 0.3, // ⬆️ Increased from 0.18 (67% stronger)
      width: '3px',
      height: '500px',
      position: { top: '0', left: '30%' },
    },
  ],

  // Layer 6: Colorful accent dots (NEW! - visual anchors for transparency effect)
  accentDots: [
    {
      color: 'rgba(99, 102, 241, 0.15)', // Indigo-500
      size: '120px',
      blur: '60px',
      position: { top: '15%', left: '25%' },
    },
    {
      color: 'rgba(236, 72, 153, 0.12)', // Pink-500
      size: '100px',
      blur: '50px',
      position: { bottom: '20%', right: '30%' },
    },
  ],
}
