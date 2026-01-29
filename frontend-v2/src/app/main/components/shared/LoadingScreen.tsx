/**
 * Loading Screen - Displayed while loading Mosaics
 * Dual-theme support with consistent backdrop styling
 */

import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTheme } from "../../hooks/useTheme"

export function LoadingScreen() {
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

  return (
    <div
      className={cn(
        "flex h-screen w-full items-center justify-center",
        !isAppleGlass && "bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950"
      )}
      style={
        isAppleGlass
          ? {
              // Apple Glass: Light background matching canvas
              background: 'var(--color-background)',
            }
          : undefined
      }
    >
      {/* Loading content container */}
      <div
        className={cn(
          "text-center px-8 py-6 rounded-2xl border",
          !isAppleGlass && "border-cyan-400/20 bg-slate-900/50 backdrop-blur-xl"
        )}
        style={
          isAppleGlass
            ? {
                // Apple Glass: Glass card effect
                background: 'var(--glass-background)',
                backdropFilter: 'var(--backdrop-blur)',
                borderColor: 'var(--glass-border)',
                boxShadow: 'var(--shadow-glass), var(--shadow-glassInset)',
              }
            : undefined
        }
      >
        {/* Spinner */}
        <Loader2
          className={cn(
            "h-12 w-12 animate-spin mx-auto mb-4",
            !isAppleGlass && "text-cyan-400"
          )}
          style={isAppleGlass ? { color: 'var(--color-primary)' } : undefined}
        />

        {/* Loading text */}
        <div
          className={cn("font-mono", !isAppleGlass && "text-cyan-300")}
          style={isAppleGlass ? { color: 'var(--color-text-primary)' } : undefined}
        >
          Loading Mosaics...
        </div>
      </div>
    </div>
  )
}
