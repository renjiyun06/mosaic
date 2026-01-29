/**
 * Target Node Selection Dialog - Select target node for connection creation
 */

import { motion } from "framer-motion"
import { X, Search, ArrowRight } from "lucide-react"
import { useState } from "react"
import { NODE_TYPE_CONFIG } from "../../constants"
import type { Node } from "@xyflow/react"
import { useTheme } from "../../hooks/useTheme"

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
  const { theme } = useTheme()
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
      {/* Backdrop Overlay */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onCancel}
        className="fixed inset-0 z-[100]"
        style={{
          background: 'var(--backdrop-overlay-bg)',
          backdropFilter: 'var(--backdrop-overlay-blur)',
        }}
      />

      {/* Dialog */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 20 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="fixed left-1/2 top-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl"
        style={{
          background: 'var(--glass-background)',
          backdropFilter: 'var(--backdrop-blur)',
          border: `var(--border-width) solid var(--glass-border)`,
          boxShadow: theme === 'cyberpunk'
            ? 'var(--neon-glow), var(--shadow-card)'
            : 'var(--shadow-glass), var(--shadow-glass-inset)',
        }}
      >
        {/* Neon Top Accent - Cyberpunk Only */}
        {theme === 'cyberpunk' && (
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />
        )}

        {/* Header */}
        <div
          className="flex items-center justify-between p-4"
          style={{
            borderBottom: `1px solid var(--glass-border)`,
          }}
        >
          <div>
            <h3
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
              {title}
            </h3>
            {sourceNodeId && (
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
                From: <span className="font-mono" style={{ color: 'var(--color-accent)' }}>{sourceNodeId}</span>
              </p>
            )}
            {description && !sourceNodeId && (
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
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onCancel}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 transition-colors focus:outline-none focus:ring-2"
            style={{
              border: `var(--border-width) solid var(--glass-border)`,
              background: 'var(--glass-background-light)',
              color: 'var(--color-text-muted)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-accent)'
              e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)'
              e.currentTarget.style.color = 'var(--color-accent)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--glass-border)'
              e.currentTarget.style.background = 'var(--glass-background-light)'
              e.currentTarget.style.color = 'var(--color-text-muted)'
            }}
            onFocus={(e) => {
              e.currentTarget.style.outline = '2px solid var(--color-accent)'
              e.currentTarget.style.outlineOffset = '2px'
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = 'none'
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Search Box */}
        <div className="p-4" style={{ borderBottom: `1px solid var(--glass-border)` }}>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search nodes..."
              aria-label="Search nodes"
              className="w-full rounded-lg py-2 pl-10 pr-3 text-sm transition-all focus:outline-none focus:ring-2"
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
              autoFocus
            />
          </div>
        </div>

        {/* Node List */}
        <div className="max-h-[400px] overflow-y-auto p-4 cyberpunk-scrollbar">
          {filteredNodes.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
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
                    className="group flex w-full items-center gap-3 rounded-lg p-3 text-left transition-all focus:outline-none focus:ring-2"
                    style={{
                      border: `var(--border-width) solid var(--glass-border)`,
                      background: 'var(--glass-background-light)',
                      backdropFilter: 'var(--backdrop-blur)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-accent)'
                      e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)'
                      if (theme === 'cyberpunk') {
                        e.currentTarget.style.boxShadow = '0 0 15px rgba(34, 211, 238, 0.2)'
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--glass-border)'
                      e.currentTarget.style.background = 'var(--glass-background-light)'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.outline = '2px solid var(--color-accent)'
                      e.currentTarget.style.outlineOffset = '2px'
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.outline = 'none'
                    }}
                  >
                    {/* Node Icon */}
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                      style={{
                        background: 'var(--glass-background-light)',
                        border: `var(--border-width) solid var(--glass-border)`,
                      }}
                    >
                      {IconComponent && (
                        <IconComponent className="h-5 w-5" style={{ color: 'var(--color-accent)' }} />
                      )}
                    </div>

                    {/* Node Info */}
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-sm font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
                        {node.id}
                      </div>
                      <div className="mt-0.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                        {nodeConfig?.label || node.data.type}
                      </div>
                    </div>

                    {/* Arrow */}
                    <ArrowRight className="h-4 w-4 shrink-0 transition-colors" style={{ color: 'var(--color-text-muted)' }} />
                  </motion.button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4" style={{ borderTop: `1px solid var(--glass-border)` }}>
          <button
            onClick={onCancel}
            className="w-full rounded-lg py-2 text-sm font-medium transition-all focus:outline-none focus:ring-2"
            style={{
              border: `var(--border-width) solid var(--glass-border)`,
              background: 'var(--glass-background-light)',
              color: 'var(--color-text-secondary)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)'
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
        </div>
      </motion.div>
    </>
  )
}
