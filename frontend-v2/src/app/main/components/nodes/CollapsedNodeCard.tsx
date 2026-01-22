/**
 * Collapsed Node Card - Small node card in collapsed state
 */

import { motion } from "framer-motion"
import { Settings, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { type NodeProps } from "@xyflow/react"
import { NODE_TYPE_CONFIG } from "../../constants"

export function CollapsedNodeCard({ data, selected }: NodeProps) {
  const incomingCount = data.incomingConnections || 0
  const outgoingCount = data.outgoingConnections || 0

  // Get icon component based on node type
  const nodeConfig = NODE_TYPE_CONFIG.find(config => config.value === data.type)
  const IconComponent = nodeConfig?.icon

  return (
    <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        whileHover={{ y: -2 }}
        onClick={() => data.onExpand()}
        className={cn(
          "group relative w-64 rounded-2xl border backdrop-blur-xl transition-all duration-300",
          selected
            ? "border-cyan-400/80 shadow-[0_0_30px_rgba(34,211,238,0.4)]"
            : "border-white/20 shadow-[0_0_15px_rgba(59,130,246,0.2)]",
          "bg-gradient-to-br from-slate-900/90 to-slate-800/90",
          "cursor-pointer"
        )}
      >

      {/* Neon top accent */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

      {/* Connection badges in top corners */}
      {(incomingCount > 0 || outgoingCount > 0) && (
        <div className="absolute -top-3 left-0 right-0 flex justify-between px-3">
          {incomingCount > 0 && (
            <motion.button
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              onClick={(e) => {
                e.stopPropagation()
                data.onShowConnections?.("incoming")
              }}
              className="group flex items-center gap-1 rounded-lg border border-blue-400/50 bg-slate-900/95 px-2 py-1 shadow-lg backdrop-blur-xl transition-all hover:border-blue-400/80 hover:shadow-[0_0_15px_rgba(59,130,246,0.3)]"
            >
              <ArrowRight className="h-3 w-3 rotate-180 text-blue-400" />
              <span className="font-mono text-xs font-semibold text-blue-300">{incomingCount}</span>
            </motion.button>
          )}
          {outgoingCount > 0 && (
            <motion.button
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              onClick={(e) => {
                e.stopPropagation()
                data.onShowConnections?.("outgoing")
              }}
              className="group flex items-center gap-1 rounded-lg border border-emerald-400/50 bg-slate-900/95 px-2 py-1 shadow-lg backdrop-blur-xl transition-all hover:border-emerald-400/80 hover:shadow-[0_0_15px_rgba(52,211,153,0.3)]"
            >
              <span className="font-mono text-xs font-semibold text-emerald-300">{outgoingCount}</span>
              <ArrowRight className="h-3 w-3 text-emerald-400" />
            </motion.button>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 p-4">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-2 w-2 rounded-full animate-pulse",
              data.status === "running" ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-slate-500"
            )}
          />
          <span className="font-mono text-sm font-semibold text-cyan-300">{data.id}</span>
        </div>
        <div
          className={cn(
            "rounded-md px-2 py-0.5 text-xs font-medium",
            data.status === "running" ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-600/50 text-slate-400"
          )}
        >
          {data.status === "running" ? "RUNNING" : "STOPPED"}
        </div>
      </div>

      {/* Body */}
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2 text-slate-300">
          {IconComponent && <IconComponent className="h-4 w-4 text-cyan-400" />}
          <span className="text-sm font-medium">{nodeConfig?.label || data.type}</span>
        </div>

        {/* Active Sessions Count - Compact */}
        <div className="flex justify-between text-xs text-slate-400">
          <span>Active Sessions</span>
          <span className="font-mono text-cyan-300">{data.sessions || 0}</span>
        </div>
      </div>

      {/* Footer actions */}
      <div className="flex gap-2 border-t border-white/10 p-3">
        <button
          onClick={(e) => e.stopPropagation()}
          className="flex-1 rounded-lg bg-cyan-500/20 py-1.5 text-xs font-medium text-cyan-300 transition-colors hover:bg-cyan-500/30"
        >
          Start
        </button>
        <button
          onClick={(e) => e.stopPropagation()}
          className="flex-1 rounded-lg bg-white/5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10"
        >
          Stop
        </button>
        <button
          onClick={(e) => e.stopPropagation()}
          className="rounded-lg bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10"
        >
          <Settings className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Glow effect on running nodes */}
      {data.status === "running" && (
        <div className="pointer-events-none absolute inset-0 rounded-2xl bg-cyan-400/5" />
      )}
    </motion.div>
  )
}
