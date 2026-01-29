/**
 * Create Connection Dialog - Unified form for creating connections
 */

import { useState } from "react"
import { motion } from "framer-motion"
import { X, ArrowRight, Check, ChevronDown } from "lucide-react"
import { SessionAlignment } from "@/lib/types"
import { NODE_TYPE_CONFIG } from "../../constants"
import type { Node } from "@xyflow/react"
import { useTheme } from "../../hooks/useTheme"

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
  const { theme } = useTheme()
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

      {/* Dialog Container */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.8, opacity: 0 }}
        transition={{ type: "spring", damping: 20, stiffness: 200 }}
        className="fixed left-1/2 top-1/2 z-[101] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-3xl"
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
              Create Connection
            </h3>
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
              Connect nodes to enable event flow
            </p>
          </div>
          <button
            onClick={onCancel}
            aria-label="Close dialog"
            className="group rounded-xl p-2 transition-all focus:outline-none focus:ring-2"
            style={{
              border: `var(--border-width) solid var(--glass-border)`,
              background: 'var(--glass-background-light)',
              color: 'var(--color-text-secondary)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)'
              e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'
              e.currentTarget.style.color = '#fca5a5'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--glass-border)'
              e.currentTarget.style.background = 'var(--glass-background-light)'
              e.currentTarget.style.color = 'var(--color-text-secondary)'
            }}
            onFocus={(e) => {
              e.currentTarget.style.outline = '2px solid var(--color-accent)'
              e.currentTarget.style.outlineOffset = '2px'
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = 'none'
            }}
          >
            <X className="h-5 w-5" />
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
                className="w-full appearance-none rounded-xl px-3 py-2.5 pr-9 font-mono text-sm transition-all cursor-pointer focus:outline-none focus:ring-2"
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
              >
                <option value="" style={{ background: 'var(--color-background)', color: 'var(--color-text-muted)' }}>
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
                      style={{ background: 'var(--color-background)', color: 'var(--color-text-primary)' }}
                    >
                      {node.id}
                    </option>
                  )
                })}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--color-text-muted)' }} />
            </div>

            <ArrowRight className="h-5 w-5 shrink-0" style={{ color: 'var(--color-accent)' }} />

            <div className="relative flex-1">
              <select
                value={targetNodeId}
                onChange={(e) => setTargetNodeId(e.target.value)}
                className="w-full appearance-none rounded-xl px-3 py-2.5 pr-9 font-mono text-sm transition-all cursor-pointer focus:outline-none focus:ring-2"
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
              >
                <option value="" style={{ background: 'var(--color-background)', color: 'var(--color-text-muted)' }}>
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
                      style={{ background: 'var(--color-background)', color: 'var(--color-text-primary)' }}
                    >
                      {node.id}
                    </option>
                  )
                })}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--color-text-muted)' }} />
            </div>
          </div>

          {/* Session Alignment Strategy */}
          <div className="space-y-2">
            <label className="block text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
              Session Alignment
            </label>
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
                    className="relative flex flex-col items-center gap-2 rounded-xl p-3 transition-all cursor-pointer focus:outline-none focus:ring-2"
                    style={{
                      border: isSelected
                        ? `var(--border-width) solid var(--color-accent)`
                        : `var(--border-width) solid var(--glass-border)`,
                      background: isSelected
                        ? 'rgba(59, 130, 246, 0.15)'
                        : 'var(--glass-background-light)',
                      backdropFilter: 'var(--backdrop-blur)',
                      boxShadow: isSelected && theme === 'cyberpunk'
                        ? '0 0 15px rgba(34, 211, 238, 0.2)'
                        : 'none',
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
                      className="text-xs font-semibold text-center"
                      style={{
                        color: isSelected ? 'var(--color-accent)' : 'var(--color-text-secondary)'
                      }}
                    >
                      {option.label}
                    </span>
                    {isSelected && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute right-2 top-2"
                      >
                        <Check className="h-3.5 w-3.5" style={{ color: 'var(--color-accent)' }} />
                      </motion.div>
                    )}
                  </motion.button>
                )
              })}
            </div>
            <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
              {SESSION_ALIGNMENT_OPTIONS.find(opt => opt.value === sessionAlignment)?.description}
            </p>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="block text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
              Description (Optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the purpose of this connection..."
              rows={3}
              maxLength={500}
              className="w-full resize-none rounded-xl px-3 py-2.5 text-sm transition-all cyberpunk-scrollbar-thin focus:outline-none focus:ring-2"
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
            <div className="text-right text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {description.length}/500
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          className="relative z-10 flex gap-3 p-5"
          style={{
            borderTop: `1px solid var(--glass-border)`,
            background: 'var(--glass-background-light)',
          }}
        >
          <button
            onClick={onCancel}
            className="flex-1 rounded-xl py-3 text-sm font-medium transition-all focus:outline-none focus:ring-2"
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
          <button
            onClick={handleConfirm}
            disabled={!isValid}
            className="flex-1 rounded-xl py-3 text-sm font-medium transition-all focus:outline-none focus:ring-2"
            style={{
              border: isValid
                ? `var(--border-width) solid var(--color-accent)`
                : `var(--border-width) solid var(--glass-border)`,
              background: isValid
                ? 'rgba(59, 130, 246, 0.15)'
                : 'var(--glass-background-light)',
              color: isValid ? 'var(--color-accent)' : 'var(--color-text-muted)',
              cursor: isValid ? 'pointer' : 'not-allowed',
              opacity: isValid ? '1' : '0.5',
            }}
            onMouseEnter={(e) => {
              if (isValid) {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)'
                if (theme === 'cyberpunk') {
                  e.currentTarget.style.boxShadow = '0 0 20px rgba(34, 211, 238, 0.3)'
                }
              }
            }}
            onMouseLeave={(e) => {
              if (isValid) {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                e.currentTarget.style.boxShadow = 'none'
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
            Create Connection
          </button>
        </div>
      </motion.div>
    </>
  )
}
