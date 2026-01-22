/**
 * Keyboard shortcuts hook
 */

import { useEffect } from "react"

interface KeyboardShortcutHandlers {
  onOpenCommand: () => void
  onCloseCommand: () => void
}

export function useKeyboardShortcuts(handlers: KeyboardShortcutHandlers) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        handlers.onOpenCommand()
      }
      if (e.key === "Escape") {
        handlers.onCloseCommand()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handlers])
}
