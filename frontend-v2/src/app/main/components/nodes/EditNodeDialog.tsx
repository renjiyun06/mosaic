/**
 * Edit Node Dialog - Dialog for editing existing node properties
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import * as Dialog from "@radix-ui/react-dialog"
import { Edit, X, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTheme } from "../../hooks/useTheme"

interface EditNodeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  nodeId: string
  nodeName?: string
  initialDescription?: string | null
  initialConfig?: Record<string, any> | null
  initialAutoStart?: boolean
  onSave: (data: {
    description?: string | null
    config?: Record<string, any> | null
    auto_start?: boolean | null
  }) => Promise<void>
}

export function EditNodeDialog({
  open,
  onOpenChange,
  nodeId,
  nodeName,
  initialDescription = "",
  initialConfig = {},
  initialAutoStart = true,
  onSave,
}: EditNodeDialogProps) {
  const { theme } = useTheme()
  const [description, setDescription] = useState("")
  const [config, setConfig] = useState("{}")
  const [autoStart, setAutoStart] = useState(true)
  const [configError, setConfigError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Initialize form values when dialog opens
  useEffect(() => {
    if (open) {
      setDescription(initialDescription || "")
      setConfig(initialConfig ? JSON.stringify(initialConfig, null, 2) : "{}")
      setAutoStart(initialAutoStart)
      setConfigError(null)
    }
  }, [open, initialDescription, initialConfig, initialAutoStart])

  const handleSave = async () => {
    // Validate JSON config
    try {
      JSON.parse(config)
      setConfigError(null)
    } catch (e) {
      setConfigError("Invalid JSON format")
      return
    }

    try {
      setSaving(true)
      await onSave({
        description: description.trim() || null,
        config: config.trim() ? JSON.parse(config) : null,
        auto_start: autoStart,
      })
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to update node:", error)
      // Keep dialog open on error
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop Overlay */}
              <Dialog.Overlay asChild>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[150]"
                  style={{
                    background: 'var(--backdrop-overlay-bg)',
                    backdropFilter: 'var(--backdrop-overlay-blur)',
                  }}
                />
              </Dialog.Overlay>

              {/* Dialog Content */}
              <Dialog.Content asChild>
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: 20 }}
                  transition={{ type: "spring", damping: 25, stiffness: 300 }}
                  className="fixed left-1/2 top-1/2 z-[200] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-3xl"
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
                        <Edit className="h-5 w-5" style={{ color: 'var(--color-accent)' }} />
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
                          Edit Node
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
                          <span className="font-mono" style={{ color: 'var(--color-accent)' }}>{nodeId}</span>
                          {nodeName && <span> - {nodeName}</span>}
                        </p>
                      </div>
                    </div>
                    <Dialog.Close
                      className="group rounded-xl p-2 transition-all focus:outline-none focus:ring-2"
                      style={{
                        border: `var(--border-width) solid var(--glass-border)`,
                        background: 'var(--glass-background-light)',
                        color: 'var(--color-text-secondary)',
                      }}
                      onMouseEnter={(e: React.MouseEvent<HTMLButtonElement>) => {
                        e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)'
                        e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'
                        e.currentTarget.style.color = '#fca5a5'
                      }}
                      onMouseLeave={(e: React.MouseEvent<HTMLButtonElement>) => {
                        e.currentTarget.style.borderColor = 'var(--glass-border)'
                        e.currentTarget.style.background = 'var(--glass-background-light)'
                        e.currentTarget.style.color = 'var(--color-text-secondary)'
                      }}
                      onFocus={(e: React.MouseEvent<HTMLButtonElement>) => {
                        e.currentTarget.style.outline = '2px solid var(--color-accent)'
                        e.currentTarget.style.outlineOffset = '2px'
                      }}
                      onBlur={(e: React.MouseEvent<HTMLButtonElement>) => {
                        e.currentTarget.style.outline = 'none'
                      }}
                    >
                      <X className="h-5 w-5" />
                    </Dialog.Close>
                  </div>

                  {/* Form */}
                  <div className="relative z-10 max-h-[60vh] space-y-5 overflow-y-auto p-6 cyberpunk-scrollbar">
                    {/* Description Input */}
                    <div className="space-y-2">
                      <label className="block text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                        Description
                        <span className="ml-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>(optional)</span>
                      </label>
                      <div className="relative">
                        <textarea
                          value={description}
                          onChange={(e) => setDescription(e.target.value)}
                          placeholder="Describe this node's purpose..."
                          maxLength={1000}
                          rows={3}
                          className="w-full rounded-xl px-4 py-3 text-sm transition-all resize-none cyberpunk-scrollbar-thin focus:outline-none focus:ring-2"
                          style={{
                            border: `var(--border-width) solid var(--glass-border)`,
                            background: 'var(--glass-background-light)',
                            backdropFilter: 'var(--backdrop-blur)',
                            color: 'var(--color-text-primary)',
                          }}
                          onFocus={(e) => {
                            e.currentTarget.style.borderColor = 'var(--color-accent)'
                            e.currentTarget.style.outline = '2px solid var(--color-accent)'
                            e.currentTarget.style.outlineOffset = '0px'
                          }}
                          onBlur={(e) => {
                            e.currentTarget.style.borderColor = 'var(--glass-border)'
                            e.currentTarget.style.outline = 'none'
                          }}
                        />
                        <div className="mt-1 text-right text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {description.length}/1000
                        </div>
                      </div>
                    </div>

                    {/* Configuration JSON Input */}
                    <div className="space-y-2">
                      <label className="block text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                        Configuration
                        <span className="ml-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>(JSON format)</span>
                      </label>
                      <div className="relative">
                        <textarea
                          value={config}
                          onChange={(e) => {
                            setConfig(e.target.value)
                            setConfigError(null)
                          }}
                          placeholder='{"key": "value"}'
                          rows={6}
                          className="w-full rounded-xl px-4 py-3 font-mono text-sm transition-all resize-none cyberpunk-scrollbar-thin focus:outline-none focus:ring-2"
                          style={{
                            border: configError
                              ? `var(--border-width) solid rgba(239, 68, 68, 0.5)`
                              : `var(--border-width) solid var(--glass-border)`,
                            background: 'var(--glass-background-light)',
                            backdropFilter: 'var(--backdrop-blur)',
                            color: 'var(--color-text-primary)',
                          }}
                          onFocus={(e) => {
                            if (!configError) {
                              e.currentTarget.style.borderColor = 'var(--color-accent)'
                              e.currentTarget.style.outline = '2px solid var(--color-accent)'
                            } else {
                              e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)'
                              e.currentTarget.style.outline = '2px solid rgba(239, 68, 68, 0.5)'
                            }
                            e.currentTarget.style.outlineOffset = '0px'
                          }}
                          onBlur={(e) => {
                            if (!configError) {
                              e.currentTarget.style.borderColor = 'var(--glass-border)'
                            } else {
                              e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)'
                            }
                            e.currentTarget.style.outline = 'none'
                          }}
                        />
                        {configError && (
                          <p className="mt-1 text-xs" role="alert" style={{ color: '#fca5a5' }}>{configError}</p>
                        )}
                      </div>
                    </div>

                    {/* Auto Start Toggle */}
                    <div
                      className="flex items-center justify-between rounded-xl p-4"
                      style={{
                        border: `var(--border-width) solid var(--glass-border)`,
                        background: 'var(--glass-background-light)',
                        backdropFilter: 'var(--backdrop-blur)',
                      }}
                    >
                      <div>
                        <p className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>Auto Start</p>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Start node automatically when mosaic starts</p>
                      </div>
                      <button
                        onClick={() => setAutoStart(!autoStart)}
                        aria-label={`Toggle auto start ${autoStart ? 'off' : 'on'}`}
                        className="relative h-6 w-11 rounded-full transition-colors focus:outline-none focus:ring-2"
                        style={{
                          background: autoStart ? 'var(--color-accent)' : 'rgba(100, 116, 139, 1)',
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.outline = '2px solid var(--color-accent)'
                          e.currentTarget.style.outlineOffset = '2px'
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.outline = 'none'
                        }}
                      >
                        <span
                          className={cn(
                            "absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform shadow-lg",
                            autoStart ? "left-[22px]" : "left-0.5"
                          )}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Actions */}
                  <div
                    className="relative z-10 flex gap-3 p-5"
                    style={{
                      borderTop: `1px solid var(--glass-border)`,
                      background: 'var(--glass-background-light)',
                    }}
                  >
                    <button
                      onClick={() => onOpenChange(false)}
                      disabled={saving}
                      className="flex-1 rounded-xl py-3 text-sm font-medium transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        border: `var(--border-width) solid var(--glass-border)`,
                        background: 'var(--glass-background-light)',
                        color: 'var(--color-text-secondary)',
                      }}
                      onMouseEnter={(e) => {
                        if (!saving) {
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
                      onClick={handleSave}
                      disabled={saving}
                      className="flex-1 rounded-xl py-3 text-sm font-medium transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        border: `var(--border-width) solid var(--color-accent)`,
                        background: 'rgba(59, 130, 246, 0.15)',
                        color: 'var(--color-accent)',
                        boxShadow: theme === 'cyberpunk' ? '0 0 20px rgba(34, 211, 238, 0.3)' : 'var(--shadow-button)',
                      }}
                      onMouseEnter={(e) => {
                        if (!saving) {
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
                      {saving ? (
                        <span className="flex items-center justify-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Saving...
                        </span>
                      ) : (
                        "Save Changes"
                      )}
                    </button>
                  </div>
                </motion.div>
              </Dialog.Content>
            </>
          )}
        </AnimatePresence>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
