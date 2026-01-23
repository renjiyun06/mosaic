/**
 * Target Node Selection Dialog - Select target node for connection creation
 */

import { motion } from "framer-motion"
import { X, Search, ArrowRight } from "lucide-react"
import { useState } from "react"
import { NODE_TYPE_CONFIG } from "../../constants"
import type { Node } from "@xyflow/react"

interface TargetNodeSelectionDialogProps {
  sourceNodeId: string | null
  availableNodes: Node[]
  onSelectTarget: (targetNodeId: string) => void
  onCancel: () => void
  title?: string
  description?: string
}

export function TargetNodeSelectionDialog({
  sourceNodeId,
  availableNodes,
  onSelectTarget,
  onCancel,
  title = "Select Target Node",
  description,
}: TargetNodeSelectionDialogProps) {
  const [searchQuery, setSearchQuery] = useState("")

  // Filter out source node (if provided) and apply search
  const filteredNodes = availableNodes
    .filter((node) => !sourceNodeId || node.id !== sourceNodeId)
    .filter((node) =>
      node.id.toLowerCase().includes(searchQuery.toLowerCase())
    )

  const handleSelectNode = (nodeId: string) => {
    onSelectTarget(nodeId)
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

      {/* Dialog */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 20 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="fixed left-1/2 top-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-cyan-400/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_40px_rgba(34,211,238,0.3)] backdrop-blur-2xl"
      >
        {/* Neon top accent */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 p-4">
          <div>
            <h3 className="font-mono text-lg font-bold text-cyan-300">
              {title}
            </h3>
            {sourceNodeId && (
              <p className="mt-1 text-xs text-slate-400">
                From: <span className="font-mono text-cyan-400">{sourceNodeId}</span>
              </p>
            )}
            {description && !sourceNodeId && (
              <p className="mt-1 text-xs text-slate-400">
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onCancel}
            className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-slate-400 transition-colors hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:text-cyan-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Search Box */}
        <div className="border-b border-white/10 p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search nodes..."
              className="w-full rounded-lg border border-white/10 bg-slate-800/50 py-2 pl-10 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20"
              autoFocus
            />
          </div>
        </div>

        {/* Node List */}
        <div className="max-h-[400px] overflow-y-auto p-4 cyberpunk-scrollbar">
          {filteredNodes.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-slate-400">
                {searchQuery ? "No nodes found" : "No available target nodes"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredNodes.map((node) => {
                const nodeConfig = NODE_TYPE_CONFIG.find(
                  (config) => config.value === node.data.type
                )
                const IconComponent = nodeConfig?.icon

                return (
                  <motion.button
                    key={node.id}
                    onClick={() => handleSelectNode(node.id)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="group flex w-full items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 text-left transition-all hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                  >
                    {/* Node Icon */}
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-800/50 border border-white/10">
                      {IconComponent && (
                        <IconComponent className="h-5 w-5 text-cyan-400" />
                      )}
                    </div>

                    {/* Node Info */}
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-sm font-semibold text-white truncate">
                        {node.id}
                      </div>
                      <div className="mt-0.5 text-xs text-slate-400">
                        {nodeConfig?.label || node.data.type}
                      </div>
                    </div>

                    {/* Arrow */}
                    <ArrowRight className="h-4 w-4 shrink-0 text-slate-500 transition-colors group-hover:text-cyan-400" />
                  </motion.button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-white/10 p-4">
          <button
            onClick={onCancel}
            className="w-full rounded-lg border border-white/20 bg-white/5 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10"
          >
            Cancel
          </button>
        </div>
      </motion.div>
    </>
  )
}
