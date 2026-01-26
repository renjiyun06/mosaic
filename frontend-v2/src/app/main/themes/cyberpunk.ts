/**
 * Mosaic Theme - Cyberpunk
 *
 * Dark neon sci-fi theme with strong visual impact
 * - Card opacity: 95% (frosted glass)
 * - Blur: 20px (strong blur)
 * - Border: 1px cyan with neon glow
 * - Shadows: Neon glow effects
 *
 * Best for: Night mode, tech demos, sci-fi aesthetic
 */

import { ThemeTokens } from './tokens'

export const cyberpunkTheme: ThemeTokens = {
  name: 'cyberpunk',

  // Color Palette - Neon Sci-Fi
  colors: {
    primary: '#00FFFF',        // Cyan neon (main accent)
    secondary: '#7B61FF',      // Purple (secondary accent)
    accent: '#FF00FF',         // Magenta (CTA)
    background: '#050510',     // Deep dark blue-black
    backgroundDots: '#1e293b', // Slate-800 for ReactFlow dots
    surface: '#0F1419',        // Slightly lighter surface
    text: {
      primary: '#E0E0FF',      // Light lavender (14.2:1 contrast)
      secondary: '#94A3B8',    // Muted gray
      muted: '#64748B',        // Darker muted
    },
    border: '#22d3ee',         // Cyan-400 border
    success: '#10b981',        // Emerald-500
    warning: '#f59e0b',        // Amber-500
    error: '#ef4444',          // Red-500
  },

  // Glass & Blur Effects - Frosted Glass
  glass: {
    background: 'rgba(15, 20, 25, 0.95)',      // 95% opacity (strong frosted)
    backgroundLight: 'rgba(15, 20, 25, 0.85)', // 85% opacity (lighter frosted)
    blur: '20px',                               // Strong blur
    border: 'rgba(34, 211, 238, 0.2)',         // Cyan border with 20% opacity
  },

  // Shadows & Glows - Neon Effects
  shadows: {
    neon: '0 0 30px rgba(34, 211, 238, 0.3)',                    // Standard neon glow
    neonHover: '0 0 40px rgba(34, 211, 238, 0.5)',               // Stronger glow on hover
    neonStrong: '0 0 50px rgba(34, 211, 238, 0.4)',              // Strongest glow
    card: '0 8px 32px rgba(0, 0, 0, 0.5)',                       // Card drop shadow
    cardInset: 'inset 0 1px 0 rgba(34, 211, 238, 0.1)',          // Inner highlight
    button: '0 0 20px rgba(0, 255, 255, 0.4)',                   // Button glow
  },

  // Typography - Space Fonts
  fonts: {
    heading: 'Space Grotesk, sans-serif',
    body: 'DM Sans, sans-serif',
    mono: 'Fira Code, monospace',
  },

  // Effects - Sharp and Precise
  effects: {
    borderWidth: '1px',                // Standard border width
    borderRadius: {
      small: '0.5rem',                 // 8px
      medium: '1rem',                  // 16px
      large: '1.5rem',                 // 24px
      xl: '2rem',                      // 32px
    },
    backdropBlur: 'blur(20px)',        // Strong backdrop blur
    transition: '300ms ease-out',      // Smooth transitions
  },
}
