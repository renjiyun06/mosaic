/**
 * Create Connection Dialog - Unified form for creating connections
 */

import { useState } from "react"
import { motion } from "framer-motion"
import { X, ArrowRight, Check, ChevronDown } from "lucide-react"
import { SessionAlignment } from "@/lib/types"
import { NODE_TYPE_CONFIG } from "../../constants"
import type { Node } from "@xyflow/react"

interface CreateConnectionDialogProps {
  availableNodes: Node[]
  onConfirm: (
    sourceNodeId: string,
    targetNodeId: string,
    sessionAlignment: SessionAlignment,
    description: string
  ) => void
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

export function CreateConnectionDialog({
  availableNodes,
  onConfirm,
  onCancel,
}: CreateConnectionDialogProps) {
  const [sourceNodeId, setSourceNodeId] = useState("")
  const [targetNodeId, setTargetNodeId] = useState("")
  const [sessionAlignment, setSessionAlignment] = useState<SessionAlignment>(
    SessionAlignment.TASKING
  )
  const [description, setDescription] = useState("")

  const handleConfirm = () => {
    if (!sourceNodeId || !targetNodeId) return
    onConfirm(sourceNodeId, targetNodeId, sessionAlignment, description)
  }

  const isValid = sourceNodeId && targetNodeId

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

      {/* Dialog */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.8, opacity: 0 }}
        transition={{ type: "spring", damping: 20, stiffness: 200 }}
        className="fixed left-1/2 top-1/2 z-[101] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-cyan-400/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_50px_rgba(34,211,238,0.4)] backdrop-blur-2xl"
      >
        {/* Animated border glow */}
        <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

        {/* Header */}
        <div className="relative z-10 flex items-center justify-between border-b border-white/10 bg-slate-900/50 p-5">
          <div>
            <h3 className="font-mono text-lg font-bold text-cyan-300">
              Create Connection
            </h3>
            <p className="text-xs text-slate-400">
              Connect nodes to enable event flow
            </p>
          </div>
          <button
            onClick={onCancel}
            className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-red-400/50 hover:bg-red-500/20"
          >
            <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-red-300" />
          </button>
        </div>

        {/* Body */}
        <div className="relative z-10 space-y-4 p-5">
          {/* Node Connection Row */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <select
                value={sourceNodeId}
                onChange={(e) => setSourceNodeId(e.target.value)}
                className="w-full appearance-none rounded-xl border border-white/20 bg-slate-800/50 px-3 py-2.5 pr-9 font-mono text-sm text-white focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl cursor-pointer transition-all"
              >
                <option value="" className="bg-slate-800 text-slate-400">
                  Select source node...
                </option>
                {availableNodes.map((node) => {
                  const nodeConfig = NODE_TYPE_CONFIG.find(
                    (config) => config.value === node.data.type
                  )
                  return (
                    <option
                      key={node.id}
                      value={node.id}
                      className="bg-slate-800 text-white"
                    >
                      {node.id}
                    </option>
                  )
                })}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>

            <ArrowRight className="h-5 w-5 shrink-0 text-cyan-400" />

            <div className="relative flex-1">
              <select
                value={targetNodeId}
                onChange={(e) => setTargetNodeId(e.target.value)}
                className="w-full appearance-none rounded-xl border border-white/20 bg-slate-800/50 px-3 py-2.5 pr-9 font-mono text-sm text-white focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl cursor-pointer transition-all"
              >
                <option value="" className="bg-slate-800 text-slate-400">
                  Select target node...
                </option>
                {availableNodes.map((node) => {
                  const nodeConfig = NODE_TYPE_CONFIG.find(
                    (config) => config.value === node.data.type
                  )
                  return (
                    <option
                      key={node.id}
                      value={node.id}
                      className="bg-slate-800 text-white"
                    >
                      {node.id}
                    </option>
                  )
                })}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Session Alignment Strategy */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">Session Alignment</label>
            <div className="grid grid-cols-3 gap-2">
              {SESSION_ALIGNMENT_OPTIONS.map((option) => {
                const isSelected = sessionAlignment === option.value
                return (
                  <motion.button
                    key={option.value}
                    type="button"
                    onClick={() => setSessionAlignment(option.value)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`relative flex flex-col items-center gap-2 rounded-xl border p-3 transition-all cursor-pointer ${
                      isSelected
                        ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                        : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10"
                    }`}
                  >
                    <span className={`text-xs font-semibold text-center ${
                      isSelected ? "text-cyan-300" : "text-slate-300"
                    }`}>
                      {option.label}
                    </span>
                    {isSelected && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute right-2 top-2"
                      >
                        <Check className="h-3.5 w-3.5 text-cyan-300" />
                      </motion.div>
                    )}
                  </motion.button>
                )
              })}
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              {SESSION_ALIGNMENT_OPTIONS.find(opt => opt.value === sessionAlignment)?.description}
            </p>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">Description (Optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the purpose of this connection..."
              rows={3}
              maxLength={500}
              className="w-full resize-none rounded-xl border border-white/20 bg-slate-800/50 px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl transition-all"
            />
            <div className="text-right text-xs text-slate-400">
              {description.length}/500
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 flex gap-3 border-t border-white/10 bg-slate-900/50 p-5">
          <button
            onClick={onCancel}
            className="flex-1 rounded-xl border border-white/20 bg-white/5 py-3 text-sm font-medium text-slate-300 transition-all hover:bg-white/10"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!isValid}
            className={`flex-1 rounded-xl border py-3 text-sm font-medium transition-all ${
              isValid
                ? "border-cyan-400/50 bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 hover:shadow-[0_0_20px_rgba(34,211,238,0.3)] cursor-pointer"
                : "border-white/10 bg-white/5 text-slate-500 cursor-not-allowed"
            }`}
          >
            Create Connection
          </button>
        </div>
      </motion.div>
    </>
  )
}
