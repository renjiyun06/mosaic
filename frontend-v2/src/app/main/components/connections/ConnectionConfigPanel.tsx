/**
 * Connection Config Panel - Floating dialog for configuring new connections
 */

import { useState } from "react"
import { motion } from "framer-motion"
import { X, ArrowRight, Check } from "lucide-react"
import { SessionAlignment } from "@/lib/types"

interface ConnectionConfigPanelProps {
  sourceNodeId: string
  targetNodeId: string
  onConfirm: (sessionAlignment: SessionAlignment, description: string) => void
  onCancel: () => void
}

// Session alignment configuration
const SESSION_ALIGNMENT_OPTIONS = [
  {
    value: SessionAlignment.MIRRORING,
    label: "Mirroring",
    description: "One-to-one session mapping. Downstream session lifecycle mirrors upstream.",
  },
  {
    value: SessionAlignment.TASKING,
    label: "Tasking",
    description: "One-to-many mapping. Creates new session for each event.",
  },
  {
    value: SessionAlignment.AGENT_DRIVEN,
    label: "Agent-Driven",
    description: "Agent controls session lifecycle with task_complete() tool.",
  },
]

export function ConnectionConfigPanel({
  sourceNodeId,
  targetNodeId,
  onConfirm,
  onCancel,
}: ConnectionConfigPanelProps) {
  const [sessionAlignment, setSessionAlignment] = useState<SessionAlignment>(
    SessionAlignment.TASKING
  )
  const [description, setDescription] = useState("")

  const handleConfirm = () => {
    onConfirm(sessionAlignment, description)
  }

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onCancel}
        className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
      />

      {/* Panel */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.8, opacity: 0 }}
        transition={{ type: "spring", damping: 20, stiffness: 300 }}
        className="fixed left-1/2 top-1/2 z-[101] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-cyan-400/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_40px_rgba(34,211,238,0.3)] backdrop-blur-2xl"
      >
        {/* Neon top accent */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 p-4">
          <h3 className="font-mono text-lg font-bold text-cyan-300">
            Configure Connection
          </h3>
          <button
            onClick={onCancel}
            className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-slate-400 transition-colors hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:text-cyan-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 p-4">
          {/* Connection Info */}
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-slate-800/50 p-3">
            <span className="flex-1 truncate font-mono text-sm font-medium text-cyan-300">
              {sourceNodeId}
            </span>
            <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
            <span className="flex-1 truncate font-mono text-sm font-medium text-cyan-300">
              {targetNodeId}
            </span>
          </div>

          {/* Session Alignment Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">
              Session Alignment Strategy *
            </label>
            <div className="space-y-2">
              {SESSION_ALIGNMENT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setSessionAlignment(option.value)}
                  className={`group w-full rounded-lg border p-3 text-left transition-all ${
                    sessionAlignment === option.value
                      ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                      : "border-white/10 bg-white/5 hover:border-cyan-400/30 hover:bg-white/10"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors ${
                        sessionAlignment === option.value
                          ? "border-cyan-400 bg-cyan-400"
                          : "border-slate-500 bg-transparent"
                      }`}
                    >
                      {sessionAlignment === option.value && (
                        <Check className="h-3 w-3 text-slate-900" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div
                        className={`text-sm font-semibold ${
                          sessionAlignment === option.value
                            ? "text-cyan-300"
                            : "text-slate-300"
                        }`}
                      >
                        {option.label}
                      </div>
                      <div className="mt-0.5 text-xs text-slate-400">
                        {option.description}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">
              Description (Optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the purpose of this connection..."
              rows={3}
              maxLength={500}
              className="w-full resize-none rounded-lg border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl cyberpunk-scrollbar-thin"
            />
            <div className="text-right text-xs text-slate-400">
              {description.length}/500
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-2 border-t border-white/10 p-4">
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-white/20 bg-white/5 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="flex-1 rounded-lg border border-cyan-400/30 bg-cyan-500/20 py-2 text-sm font-medium text-cyan-300 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/30 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
          >
            Create Connection
          </button>
        </div>
      </motion.div>
    </>
  )
}
