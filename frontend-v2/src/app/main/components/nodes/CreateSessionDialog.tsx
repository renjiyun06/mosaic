/**
 * Create Session Dialog - Dialog for creating new sessions
 */

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, X, Check, Loader2, MessageSquare, Code2, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTheme } from "../../hooks/useTheme"

interface CreateSessionDialogProps {
  nodeId: string
  onClose: () => void
  onCreate: (sessionData: { mode: string; model: string }) => Promise<void>
}

// Mode configurations with icons and descriptions
const MODE_CONFIG = [
  {
    value: "chat",
    label: "Chat",
    icon: MessageSquare,
    description: "Interactive conversation",
    color: "cyan",
  },
  {
    value: "program",
    label: "Program",
    icon: Code2,
    description: "Programming mode",
    color: "blue",
  },
  {
    value: "long_running",
    label: "Long Running",
    icon: Clock,
    description: "Background tasks",
    color: "purple",
  },
]

// Model configurations with descriptions
const MODEL_CONFIG = [
  {
    value: "sonnet",
    label: "Sonnet",
    description: "Balanced performance",
    badge: "Recommended",
  },
  {
    value: "opus",
    label: "Opus",
    description: "Maximum capability",
    badge: "Premium",
  },
  {
    value: "haiku",
    label: "Haiku",
    description: "Fast & efficient",
    badge: "Fast",
  },
]

export function CreateSessionDialog({ nodeId, onClose, onCreate }: CreateSessionDialogProps) {
  const { theme } = useTheme()
  const [mode, setMode] = useState<string>("chat")
  const [model, setModel] = useState<string>("sonnet")
  const [creating, setCreating] = useState(false)

  const handleCreate = async (e?: React.MouseEvent) => {
    // Prevent event bubbling to backdrop
    e?.stopPropagation()

    try {
      setCreating(true)
      console.log("[CreateSessionDialog] Starting session creation...")
      await onCreate({ mode, model })
      console.log("[CreateSessionDialog] Session creation completed, closing dialog")
      onClose()
    } catch (error) {
      console.error("[CreateSessionDialog] Failed to create session:", error)
      // Keep dialog open on error - do NOT call onClose()
      alert("Failed to create session. Please check the console for details.")
    } finally {
      setCreating(false)
    }
  }

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.8, opacity: 0 }}
      transition={{ type: "spring", damping: 20, stiffness: 200 }}
      className="relative w-[500px] rounded-3xl"
      style={{
        background: 'var(--glass-background)',
        backdropFilter: 'var(--backdrop-blur)',
        border: `var(--border-width) solid var(--glass-border)`,
        boxShadow: theme === 'cyberpunk'
          ? 'var(--neon-glow), var(--shadow-card)'
          : 'var(--shadow-glass), var(--shadow-glass-inset)',
      }}
    >
      {/* Neon Border Glow - Cyberpunk Only */}
      {theme === 'cyberpunk' && (
        <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />
      )}

      {/* Header */}
      <div
        className="relative z-10 flex items-center justify-between p-5"
        style={{
          borderBottom: `1px solid var(--glass-border)`,
          background: 'var(--glass-background-light)',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-xl"
            style={{
              background: 'rgba(59, 130, 246, 0.15)',
              border: `var(--border-width) solid var(--color-accent)`,
              boxShadow: theme === 'cyberpunk' ? '0 0 20px rgba(34, 211, 238, 0.5)' : 'var(--shadow-button)',
            }}
          >
            <Plus className="h-5 w-5" style={{ color: 'var(--color-accent)' }} />
          </div>
          <div>
            <h2
              className="inline-block rounded-lg px-2.5 py-1.5 font-mono text-lg font-bold"
              style={{
                color: 'var(--color-primary)',
                background: theme === 'apple-glass' ? 'var(--text-scrim-title-bg)' : 'transparent',
                backdropFilter: theme === 'apple-glass' ? 'var(--text-scrim-title-blur)' : 'none',
                border: theme === 'apple-glass' ? 'var(--text-scrim-title-border)' : 'none',
                borderRadius: theme === 'apple-glass' ? '10px' : '0',
                padding: theme === 'apple-glass' ? '6px 10px' : '0',
              }}
            >
              Create Session
            </h2>
            <p
              className="mt-1 inline-block rounded-lg px-2.5 py-1.5 text-xs"
              style={{
                color: 'var(--color-text-secondary)',
                background: theme === 'apple-glass' ? 'var(--text-scrim-subtitle-bg)' : 'transparent',
                backdropFilter: theme === 'apple-glass' ? 'var(--text-scrim-subtitle-blur)' : 'none',
                border: theme === 'apple-glass' ? 'var(--text-scrim-subtitle-border)' : 'none',
                borderRadius: theme === 'apple-glass' ? '8px' : '0',
                padding: theme === 'apple-glass' ? '5px 10px' : '0',
              }}
            >
              Node: {nodeId}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          disabled={creating}
          aria-label="Close dialog"
          className="group rounded-xl p-2 transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            border: `var(--border-width) solid var(--glass-border)`,
            background: 'var(--glass-background-light)',
            color: 'var(--color-text-secondary)',
          }}
          onMouseEnter={(e) => {
            if (!creating) {
              e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)'
              e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'
              e.currentTarget.style.color = '#fca5a5'
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--glass-border)'
            e.currentTarget.style.background = 'var(--glass-background-light)'
            e.currentTarget.style.color = 'var(--color-text-secondary)'
          }}
          onFocus={(e) => {
            e.currentTarget.style.outline = '2px solid var(--color-accent)'
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Form */}
      <div className="relative z-10 space-y-6 p-6">
        {/* Mode Selection */}
        <div className="space-y-3">
          <label className="block text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Session Mode
          </label>
          <div className="grid grid-cols-3 gap-3">
            {MODE_CONFIG.map((modeOption) => {
              const Icon = modeOption.icon
              const isSelected = mode === modeOption.value
              return (
                <motion.button
                  key={modeOption.value}
                  onClick={() => setMode(modeOption.value)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  disabled={creating}
                  className="relative flex flex-col items-center gap-2 rounded-xl p-4 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2"
                  style={{
                    border: isSelected
                      ? `var(--border-width) solid var(--color-accent)`
                      : `var(--border-width) solid var(--glass-border)`,
                    background: isSelected
                      ? 'rgba(59, 130, 246, 0.15)'
                      : 'var(--glass-background-light)',
                    backdropFilter: 'var(--backdrop-blur)',
                    boxShadow: isSelected && theme === 'cyberpunk'
                      ? '0 0 20px rgba(34, 211, 238, 0.2)'
                      : 'none',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.outline = '2px solid var(--color-accent)'
                    e.currentTarget.style.outlineOffset = '2px'
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.outline = 'none'
                  }}
                >
                  <Icon className="h-6 w-6" style={{ color: isSelected ? 'var(--color-accent)' : 'var(--color-text-muted)' }} />
                  <div className="text-center">
                    <div className="text-sm font-medium" style={{ color: isSelected ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}>
                      {modeOption.label}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                      {modeOption.description}
                    </div>
                  </div>
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute right-2 top-2"
                    >
                      <Check className="h-4 w-4" style={{ color: 'var(--color-accent)' }} />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Model Selection */}
        <div className="space-y-3">
          <label className="block text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Model
          </label>
          <div className="space-y-2">
            {MODEL_CONFIG.map((modelOption) => {
              const isSelected = model === modelOption.value
              return (
                <motion.button
                  key={modelOption.value}
                  onClick={() => setModel(modelOption.value)}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  disabled={creating}
                  className="relative w-full flex items-center justify-between rounded-xl p-4 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2"
                  style={{
                    border: isSelected
                      ? `var(--border-width) solid var(--color-accent)`
                      : `var(--border-width) solid var(--glass-border)`,
                    background: isSelected
                      ? 'rgba(59, 130, 246, 0.15)'
                      : 'var(--glass-background-light)',
                    backdropFilter: 'var(--backdrop-blur)',
                    boxShadow: isSelected && theme === 'cyberpunk'
                      ? '0 0 20px rgba(34, 211, 238, 0.2)'
                      : 'none',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.outline = '2px solid var(--color-accent)'
                    e.currentTarget.style.outlineOffset = '2px'
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.outline = 'none'
                  }}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col items-start">
                      <div className="text-sm font-medium flex items-center gap-2" style={{ color: isSelected ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}>
                        {modelOption.label}
                        <span
                          className="text-xs px-2 py-0.5 rounded-md"
                          style={{
                            background: modelOption.value === "sonnet"
                              ? 'rgba(16, 185, 129, 0.2)'
                              : modelOption.value === "opus"
                              ? 'rgba(168, 85, 247, 0.2)'
                              : 'rgba(59, 130, 246, 0.2)',
                            color: modelOption.value === "sonnet"
                              ? '#6ee7b7'
                              : modelOption.value === "opus"
                              ? '#c4b5fd'
                              : '#93c5fd',
                          }}
                        >
                          {modelOption.badge}
                        </span>
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                        {modelOption.description}
                      </div>
                    </div>
                  </div>
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                    >
                      <Check className="h-5 w-5" style={{ color: 'var(--color-accent)' }} />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        className="relative z-10 flex items-center justify-end gap-3 p-5"
        style={{
          borderTop: `1px solid var(--glass-border)`,
          background: 'var(--glass-background-light)',
        }}
      >
        <button
          onClick={onClose}
          disabled={creating}
          className="rounded-xl px-5 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            border: `var(--border-width) solid var(--glass-border)`,
            background: 'var(--glass-background-light)',
            color: 'var(--color-text-secondary)',
          }}
          onMouseEnter={(e) => {
            if (!creating) {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)'
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--glass-background-light)'
          }}
          onFocus={(e) => {
            e.currentTarget.style.outline = '2px solid var(--color-accent)'
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="rounded-xl px-5 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          style={{
            border: `var(--border-width) solid var(--color-accent)`,
            background: 'rgba(59, 130, 246, 0.15)',
            color: 'var(--color-accent)',
            boxShadow: theme === 'cyberpunk' ? '0 0 20px rgba(34, 211, 238, 0.3)' : 'var(--shadow-button)',
          }}
          onMouseEnter={(e) => {
            if (!creating) {
              e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)'
              if (theme === 'cyberpunk') {
                e.currentTarget.style.boxShadow = '0 0 30px rgba(34, 211, 238, 0.5)'
              }
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
            if (theme === 'cyberpunk') {
              e.currentTarget.style.boxShadow = '0 0 20px rgba(34, 211, 238, 0.3)'
            }
          }}
          onFocus={(e) => {
            e.currentTarget.style.outline = '2px solid var(--color-accent)'
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          {creating && <Loader2 className="h-4 w-4 animate-spin" />}
          {creating ? "Creating..." : "Create Session"}
        </button>
      </div>
    </motion.div>
  )
}
