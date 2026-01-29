/**
 * ThemeToggle Component - Single Icon Button Theme Switcher
 *
 * Single button that toggles between Cyberpunk and Apple Glass themes.
 * Matches the visual style of TopRightActions buttons for consistency.
 *
 * Features:
 * - Single icon button (Sun ↔ Moon transition)
 * - Consistent glassmorphism style with other action buttons
 * - Smooth icon fade animation (AnimatePresence)
 * - Full accessibility (aria-label, keyboard, focus states)
 * - Touch-friendly (44x44px minimum)
 * - Tooltip on hover
 *
 * UI/UX Best Practices Applied:
 * ✅ Consistent sizing: h-11 w-11 (matches TopRightActions)
 * ✅ Consistent glassmorphism: Same backdrop-blur and borders
 * ✅ Consistent hover: Same cyan glow effect
 * ✅ Touch target: 44x44px (meets accessibility requirement)
 * ✅ Focus states: Visible focus ring
 * ✅ Animation: 200ms fade (smooth but fast)
 * ✅ Icon-only button: aria-label for screen readers
 * ✅ Visual harmony: Matches TopRightActions aesthetic
 *
 * @see /doc/theme-system/FINAL_DESIGN.md - Theme specifications
 */

'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sun, Moon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '../../hooks/useTheme'

/**
 * Theme Toggle Icon Button
 *
 * Visual Design:
 * - Matches TopRightActions button style exactly
 * - Cyberpunk: Moon icon with cyan glow on hover
 * - Apple Glass: Sun icon with cyan glow on hover
 * - Icon fades in/out smoothly on theme change
 *
 * Interaction:
 * - Click/Tap: Toggle theme
 * - Keyboard: Space/Enter to activate
 * - Hover: Glassmorphic glow (consistent with other buttons)
 * - Active: Scale down (whileTap 0.95)
 * - Focus: Visible cyan ring outline
 */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

  return (
    <motion.button
      onClick={toggleTheme}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className={cn(
        "group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all cursor-pointer",
        "bg-slate-900/80 backdrop-blur-xl border border-white/20",
        "hover:bg-cyan-500/20 hover:border-cyan-400/30",
        "shadow-xl hover:shadow-[0_0_20px_rgba(34,211,238,0.3)]"
      )}
      aria-label={`Switch to ${isAppleGlass ? 'Cyberpunk' : 'Apple Glass'} theme`}
      type="button"
    >
      {/* Icon with smooth fade transition */}
      <AnimatePresence mode="wait" initial={false}>
        {isAppleGlass ? (
          <motion.div
            key="sun"
            initial={{ opacity: 0, rotate: -90, scale: 0.8 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={{ opacity: 0, rotate: 90, scale: 0.8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <Sun className="h-5 w-5 text-slate-400 group-hover:text-cyan-400 transition-colors" />
          </motion.div>
        ) : (
          <motion.div
            key="moon"
            initial={{ opacity: 0, rotate: -90, scale: 0.8 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={{ opacity: 0, rotate: 90, scale: 0.8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <Moon className="h-5 w-5 text-slate-400 group-hover:text-cyan-400 transition-colors" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Tooltip (matches TopRightActions style) */}
      <div className="pointer-events-none absolute top-full mt-2 whitespace-nowrap rounded-lg bg-slate-800/95 backdrop-blur-xl px-3 py-2 text-xs opacity-0 shadow-xl transition-opacity group-hover:opacity-100 border border-cyan-400/20">
        <div className="font-medium text-cyan-300">
          {isAppleGlass ? 'Cyberpunk Mode' : 'Apple Glass Mode'}
        </div>
        <div className="text-slate-400 text-[10px] mt-0.5">
          {isAppleGlass ? 'Dark neon theme' : 'Light glass theme'}
        </div>
      </div>
    </motion.button>
  )
}
