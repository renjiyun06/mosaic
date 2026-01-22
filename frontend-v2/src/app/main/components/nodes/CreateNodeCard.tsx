/**
 * Create Node Card - Dialog for creating new nodes
 */

import { useState } from "react"
import { motion } from "framer-motion"
import { Plus, X, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { NODE_TYPE_CONFIG } from "../../constants"

interface CreateNodeCardProps {
  onClose: () => void
  onCreate: (nodeData: any) => void
}

export function CreateNodeCard({ onClose, onCreate }: CreateNodeCardProps) {
  const [nodeId, setNodeId] = useState("")
  const [nodeType, setNodeType] = useState<"claude_code" | "email" | "scheduler" | "aggregator">("claude_code")
  const [autoStart, setAutoStart] = useState(true)

  const handleCreate = () => {
    if (nodeId.trim()) {
      onCreate({
        id: nodeId,
        type: nodeType,
        autoStart,
      })
      onClose()
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
            <h2 className="font-mono text-lg font-bold text-cyan-300">Create Node</h2>
            <p className="text-xs text-slate-400">Add new node to the mesh</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-red-400/50 hover:bg-red-500/20"
        >
          <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-red-300" />
        </button>
      </div>

      {/* Form */}
      <div className="relative z-10 space-y-5 p-6">
        {/* Node ID Input */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Node ID</label>
          <input
            type="text"
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
            placeholder="e.g., my-new-node"
            className="w-full rounded-xl border border-white/20 bg-slate-800/50 px-4 py-3 font-mono text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl transition-all"
            autoFocus
          />
        </div>

        {/* Node Type Selection */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Node Type</label>
          <div className="grid grid-cols-2 gap-3">
            {NODE_TYPE_CONFIG.map((type) => {
              const Icon = type.icon
              const isSelected = nodeType === type.value
              return (
                <motion.button
                  key={type.value}
                  onClick={() => setNodeType(type.value as any)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className={cn(
                    "relative flex items-center gap-3 rounded-xl border p-4 transition-all cursor-pointer",
                    isSelected
                      ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_20px_rgba(34,211,238,0.2)]"
                      : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10"
                  )}
                >
                  <Icon className={cn("h-5 w-5", isSelected ? "text-cyan-300" : "text-slate-400")} />
                  <span className={cn("text-sm font-medium", isSelected ? "text-cyan-300" : "text-slate-300")}>
                    {type.label}
                  </span>
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute right-3 top-1/2 -translate-y-1/2"
                    >
                      <Check className="h-4 w-4 text-cyan-300" />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Auto Start Toggle */}
        <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-4">
          <div>
            <div className="text-sm font-medium text-slate-300">Auto Start</div>
            <div className="text-xs text-slate-400">Start node automatically after creation</div>
          </div>
          <button
            onClick={() => setAutoStart(!autoStart)}
            className={cn(
              "relative h-7 w-12 rounded-full transition-all",
              autoStart ? "bg-cyan-500" : "bg-slate-600"
            )}
          >
            <motion.div
              animate={{ x: autoStart ? 20 : 2 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
              className="absolute top-1 h-5 w-5 rounded-full bg-white shadow-lg"
            />
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="relative z-10 flex gap-3 border-t border-white/10 bg-slate-900/50 p-5">
        <button
          onClick={onClose}
          className="flex-1 rounded-xl border border-white/20 bg-white/5 py-3 text-sm font-medium text-slate-300 transition-all hover:bg-white/10"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={!nodeId.trim()}
          className={cn(
            "flex-1 rounded-xl border py-3 text-sm font-medium transition-all",
            nodeId.trim()
              ? "border-cyan-400/50 bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 hover:shadow-[0_0_20px_rgba(34,211,238,0.3)] cursor-pointer"
              : "border-white/10 bg-white/5 text-slate-500 cursor-not-allowed"
          )}
        >
          Create Node
        </button>
      </div>
    </motion.div>
  )
}
