/**
 * Create Session Dialog - Dialog for creating new sessions
 */

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, X, Check, Loader2, MessageSquare, Code2, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

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
      className="relative w-[500px] rounded-3xl border border-cyan-400/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_50px_rgba(34,211,238,0.4)] backdrop-blur-2xl"
    >
      {/* Animated border glow */}
      <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

      {/* Header */}
      <div className="relative z-10 flex items-center justify-between border-b border-white/10 bg-slate-900/50 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(34,211,238,0.5)]">
            <Plus className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="font-mono text-lg font-bold text-cyan-300">Create Session</h2>
            <p className="text-xs text-slate-400">Node: {nodeId}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          disabled={creating}
          className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-red-400/50 hover:bg-red-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-red-300" />
        </button>
      </div>

      {/* Form */}
      <div className="relative z-10 space-y-6 p-6">
        {/* Mode Selection */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-slate-300">Session Mode</label>
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
                  className={cn(
                    "relative flex flex-col items-center gap-2 rounded-xl border p-4 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed",
                    isSelected
                      ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_20px_rgba(34,211,238,0.2)]"
                      : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10"
                  )}
                >
                  <Icon className={cn("h-6 w-6", isSelected ? "text-cyan-300" : "text-slate-400")} />
                  <div className="text-center">
                    <div className={cn("text-sm font-medium", isSelected ? "text-cyan-300" : "text-slate-300")}>
                      {modeOption.label}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">{modeOption.description}</div>
                  </div>
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute right-2 top-2"
                    >
                      <Check className="h-4 w-4 text-cyan-300" />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Model Selection */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-slate-300">Model</label>
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
                  className={cn(
                    "relative w-full flex items-center justify-between rounded-xl border p-4 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed",
                    isSelected
                      ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_20px_rgba(34,211,238,0.2)]"
                      : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col items-start">
                      <div className={cn("text-sm font-medium flex items-center gap-2", isSelected ? "text-cyan-300" : "text-slate-300")}>
                        {modelOption.label}
                        <span className={cn(
                          "text-xs px-2 py-0.5 rounded-md",
                          modelOption.value === "sonnet"
                            ? "bg-green-500/20 text-green-300"
                            : modelOption.value === "opus"
                            ? "bg-purple-500/20 text-purple-300"
                            : "bg-blue-500/20 text-blue-300"
                        )}>
                          {modelOption.badge}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">{modelOption.description}</div>
                    </div>
                  </div>
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                    >
                      <Check className="h-5 w-5 text-cyan-300" />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="relative z-10 flex items-center justify-end gap-3 border-t border-white/10 bg-slate-900/50 p-5">
        <button
          onClick={onClose}
          disabled={creating}
          className="rounded-xl border border-white/20 bg-white/5 px-5 py-2.5 text-sm font-medium text-slate-300 transition-all hover:border-white/30 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="rounded-xl border border-cyan-400/50 bg-gradient-to-r from-cyan-500/30 to-blue-500/30 px-5 py-2.5 text-sm font-medium text-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.3)] transition-all hover:border-cyan-400/70 hover:from-cyan-500/40 hover:to-blue-500/40 hover:shadow-[0_0_30px_rgba(34,211,238,0.5)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {creating && <Loader2 className="h-4 w-4 animate-spin" />}
          {creating ? "Creating..." : "Create Session"}
        </button>
      </div>
    </motion.div>
  )
}
