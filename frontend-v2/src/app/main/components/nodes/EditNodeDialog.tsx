/**
 * Edit Node Dialog - Dialog for editing existing node properties
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import * as Dialog from "@radix-ui/react-dialog"
import { Edit, X, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

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
              {/* Backdrop */}
              <Dialog.Overlay asChild>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[150] bg-black/60 backdrop-blur-sm"
                />
              </Dialog.Overlay>

              {/* Dialog Content */}
              <Dialog.Content asChild>
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: 20 }}
                  transition={{ type: "spring", damping: 25, stiffness: 300 }}
                  className="fixed left-1/2 top-1/2 z-[200] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-cyan-400/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_50px_rgba(34,211,238,0.4)] backdrop-blur-xl"
                >
                  {/* Animated border glow */}
                  <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

                  {/* Header */}
                  <div className="relative z-10 flex items-center justify-between border-b border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(34,211,238,0.5)]">
                        <Edit className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <h2 className="font-mono text-lg font-bold text-cyan-300">Edit Node</h2>
                        <p className="text-xs text-slate-400">
                          <span className="font-mono text-cyan-400">{nodeId}</span>
                          {nodeName && <span> - {nodeName}</span>}
                        </p>
                      </div>
                    </div>
                    <Dialog.Close className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-red-400/50 hover:bg-red-500/20">
                      <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-red-300" />
                    </Dialog.Close>
                  </div>

                  {/* Form */}
                  <div className="relative z-10 max-h-[60vh] space-y-5 overflow-y-auto p-6 cyberpunk-scrollbar">
                    {/* Description Input */}
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-slate-300">
                        Description
                        <span className="ml-2 text-xs text-slate-500">(optional)</span>
                      </label>
                      <div className="relative">
                        <textarea
                          value={description}
                          onChange={(e) => setDescription(e.target.value)}
                          placeholder="Describe this node's purpose..."
                          maxLength={1000}
                          rows={3}
                          className="w-full rounded-xl border border-white/20 bg-slate-800/50 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl transition-all resize-none cyberpunk-scrollbar-thin"
                        />
                        <div className="mt-1 text-right text-xs text-slate-500">
                          {description.length}/1000
                        </div>
                      </div>
                    </div>

                    {/* Configuration JSON Input */}
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-slate-300">
                        Configuration
                        <span className="ml-2 text-xs text-slate-500">(JSON format)</span>
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
                          className={cn(
                            "w-full rounded-xl border bg-slate-800/50 px-4 py-3 font-mono text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 backdrop-blur-xl transition-all resize-none cyberpunk-scrollbar-thin",
                            configError
                              ? "border-red-500/50 focus:border-red-400/50 focus:ring-red-400/20"
                              : "border-white/20 focus:border-cyan-400/50 focus:ring-cyan-400/20"
                          )}
                        />
                        {configError && (
                          <p className="mt-1 text-xs text-red-400">{configError}</p>
                        )}
                      </div>
                    </div>

                    {/* Auto Start Toggle */}
                    <div className="flex items-center justify-between rounded-xl border border-white/20 bg-slate-800/30 p-4 backdrop-blur-xl">
                      <div>
                        <p className="text-sm font-medium text-slate-300">Auto Start</p>
                        <p className="text-xs text-slate-500">Start node automatically when mosaic starts</p>
                      </div>
                      <button
                        onClick={() => setAutoStart(!autoStart)}
                        className={cn(
                          "relative h-6 w-11 rounded-full transition-colors",
                          autoStart ? "bg-cyan-500" : "bg-slate-600"
                        )}
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
                  <div className="relative z-10 flex gap-3 border-t border-white/10 bg-slate-900/50 p-5">
                    <button
                      onClick={() => onOpenChange(false)}
                      disabled={saving}
                      className="flex-1 rounded-xl border border-white/10 bg-white/5 py-3 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="flex-1 rounded-xl border border-cyan-400/50 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 py-3 text-sm font-medium text-cyan-300 transition-all hover:from-cyan-500/30 hover:to-blue-500/30 hover:shadow-[0_0_20px_rgba(34,211,238,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
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
