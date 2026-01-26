/**
 * Collapsed Node Card - Small node card in collapsed state
 */

import { motion } from "framer-motion"
import { Settings, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { type NodeProps } from "@xyflow/react"
import { NODE_TYPE_CONFIG } from "../../constants"
import { NodeSettingsMenu } from "./NodeSettingsMenu"
import { useTheme } from "../../hooks/useTheme"

export function CollapsedNodeCard({ data, selected }: NodeProps) {
  const { theme } = useTheme()
  const incomingCount = data.incomingConnections || 0
  const outgoingCount = data.outgoingConnections || 0

  // Get icon component based on node type
  const nodeConfig = NODE_TYPE_CONFIG.find(config => config.value === data.type)
  const IconComponent = nodeConfig?.icon

  // Only Claude Code nodes can be expanded
  const isClaudeCode = data.type === "claude_code"

  // Theme-specific flags
  const isCyberpunk = theme === 'cyberpunk'
  const isAppleGlass = theme === 'apple-glass'

  return (
    <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        whileHover={{ y: -2 }}
        onDoubleClick={isClaudeCode ? () => data.onExpand() : undefined}
        style={{
          transformOrigin: "center",
          background: 'var(--glass-background)',
          backdropFilter: 'var(--backdrop-blur)',
          borderColor: selected ? 'var(--color-primary)' : 'var(--glass-border)',
          borderWidth: 'var(--border-width)',
          boxShadow: selected
            ? (isCyberpunk ? 'var(--shadow-neonStrong)' : 'var(--shadow-glassHover)')
            : (isCyberpunk ? 'var(--shadow-neon)' : 'var(--shadow-glass)'),
        }}
        className={cn(
          "group relative w-64 rounded-2xl border transition-all duration-300",
          isClaudeCode ? "cursor-pointer" : "cursor-default"
        )}
      >

      {/* Top accent line - theme-specific */}
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background: isCyberpunk
            ? 'linear-gradient(90deg, transparent, var(--color-primary), transparent)'
            : 'linear-gradient(90deg, transparent, rgba(15, 23, 42, 0.15), transparent)', // Neutral dark line
        }}
      />

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
              style={{
                background: 'var(--glass-background)',
                backdropFilter: 'var(--backdrop-blur)',
                borderColor: isCyberpunk ? 'rgba(59, 130, 246, 0.5)' : 'rgba(59, 130, 246, 0.4)',
                borderWidth: 'var(--border-width)',
                boxShadow: 'var(--shadow-glass)',
              }}
              className="group flex items-center gap-1 rounded-lg border px-2 py-1 transition-all hover:shadow-[0_0_15px_rgba(59,130,246,0.3)]"
            >
              <ArrowRight className="h-3 w-3 rotate-180" style={{ color: 'var(--color-secondary)' }} />
              <span className="font-mono text-xs font-semibold" style={{ color: 'var(--color-secondary)' }}>{incomingCount}</span>
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
              style={{
                background: 'var(--glass-background)',
                backdropFilter: 'var(--backdrop-blur)',
                borderColor: 'var(--color-success)',
                borderWidth: 'var(--border-width)',
                boxShadow: 'var(--shadow-glass)',
              }}
              className="group flex items-center gap-1 rounded-lg border px-2 py-1 transition-all hover:shadow-[0_0_15px_rgba(52,211,153,0.3)]"
            >
              <span className="font-mono text-xs font-semibold" style={{ color: 'var(--color-success)' }}>{outgoingCount}</span>
              <ArrowRight className="h-3 w-3" style={{ color: 'var(--color-success)' }} />
            </motion.button>
          )}
        </div>
      )}

      {/* Header */}
      <div
        className="flex items-center justify-between border-b p-4"
        style={{ borderColor: 'var(--glass-border)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-2 w-2 rounded-full animate-pulse",
              data.status === "running" && "shadow-[0_0_8px_rgba(52,211,153,0.6)]"
            )}
            style={{
              backgroundColor: data.status === "running" ? 'var(--color-success)' : 'var(--color-text-muted)',
            }}
          />
          <span className="font-mono text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{data.id}</span>
        </div>
        <div
          className="rounded-md px-2 py-0.5 text-xs font-medium"
          style={{
            backgroundColor: data.status === "running"
              ? isCyberpunk ? 'rgba(52, 211, 153, 0.2)' : 'rgba(16, 185, 129, 0.15)'
              : isCyberpunk ? 'rgba(71, 85, 105, 0.5)' : 'rgba(100, 116, 139, 0.3)',
            color: data.status === "running" ? 'var(--color-success)' : 'var(--color-text-muted)',
          }}
        >
          {data.status === "running" ? "RUNNING" : "STOPPED"}
        </div>
      </div>

      {/* Body */}
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
          {IconComponent && <IconComponent className="h-4 w-4" style={{ color: 'var(--color-text-secondary)' }} />}
          <span className="text-sm font-medium">{nodeConfig?.label || data.type}</span>
        </div>

        {/* Active Sessions Count - Only for Claude Code nodes */}
        {isClaudeCode && (
          <div className="flex justify-between text-xs" style={{ color: 'var(--color-text-muted)' }}>
            <span>Active Sessions</span>
            <span className="font-mono font-semibold" style={{ color: 'var(--color-text-primary)' }}>{data.sessions || 0}</span>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div
        className="flex gap-2 border-t p-3"
        style={{ borderColor: 'var(--glass-border)' }}
      >
        <button
          onClick={(e) => e.stopPropagation()}
          style={{
            background: isCyberpunk ? 'rgba(6, 182, 212, 0.2)' : 'rgba(15, 23, 42, 0.1)', // Neutral dark for Apple Glass
            color: isCyberpunk ? 'var(--color-primary)' : 'var(--color-text-primary)',
            backdropFilter: isAppleGlass ? 'blur(8px)' : undefined,
            border: isAppleGlass ? '0.5px solid rgba(15, 23, 42, 0.15)' : undefined,
          }}
          className="flex-1 rounded-lg py-1.5 text-xs font-medium transition-colors hover:opacity-80"
        >
          Start
        </button>
        <button
          onClick={(e) => e.stopPropagation()}
          style={{
            background: isCyberpunk ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.2)',
            color: 'var(--color-text-secondary)',
            backdropFilter: isAppleGlass ? 'blur(8px)' : undefined,
            border: isAppleGlass ? '0.5px solid rgba(255, 255, 255, 0.3)' : undefined,
          }}
          className="flex-1 rounded-lg py-1.5 text-xs font-medium transition-colors hover:opacity-80"
        >
          Stop
        </button>
        <NodeSettingsMenu
          nodeId={data.id}
          onEdit={() => data.onEdit?.()}
          onDelete={() => data.onDelete?.()}
        >
          <button
            onClick={(e) => e.stopPropagation()}
            style={{
              background: isCyberpunk ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.2)',
              color: 'var(--color-text-secondary)',
              backdropFilter: isAppleGlass ? 'blur(8px)' : undefined,
              border: isAppleGlass ? '0.5px solid rgba(255, 255, 255, 0.3)' : undefined,
            }}
            className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-80"
          >
            <Settings className="h-3.5 w-3.5" />
          </button>
        </NodeSettingsMenu>
      </div>

      {/* Glow effect on running nodes */}
      {data.status === "running" && (
        <div
          className="pointer-events-none absolute inset-0 rounded-2xl"
          style={{
            background: isCyberpunk
              ? 'rgba(6, 182, 212, 0.05)'
              : 'rgba(16, 185, 129, 0.02)', // Success green glow (very subtle)
          }}
        />
      )}
    </motion.div>
  )
}
