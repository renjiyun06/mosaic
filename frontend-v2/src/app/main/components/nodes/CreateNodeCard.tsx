/**
 * Create Node Card - Dialog for creating new nodes
 */

import { useState } from "react"
import { motion } from "framer-motion"
import { Plus, X, Check, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { NODE_TYPE_CONFIG } from "../../constants"
import { useTheme } from "../../hooks/useTheme"

interface CreateNodeCardProps {
  onClose: () => void
  onCreate: (nodeData: any) => void
}

export function CreateNodeCard({ onClose, onCreate }: CreateNodeCardProps) {
  const { theme, themeTokens } = useTheme()
  const isAppleGlass = theme === 'apple-glass'
  const textScrimTokens = isAppleGlass ? themeTokens.textScrimTokens : null

  const [nodeId, setNodeId] = useState("")
  const [nodeType, setNodeType] = useState<"claude_code" | "email" | "scheduler" | "aggregator">("claude_code")
  const [description, setDescription] = useState("")
  const [config, setConfig] = useState("{}")
  const [autoStart, setAutoStart] = useState(true)
  const [configError, setConfigError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    if (!nodeId.trim()) return

    // Validate JSON config
    try {
      JSON.parse(config)
      setConfigError(null)
    } catch (e) {
      setConfigError("Invalid JSON format")
      return
    }

    try {
      setCreating(true)
      await onCreate({
        id: nodeId,
        type: nodeType,
        description: description.trim() || undefined,
        config: config.trim() ? JSON.parse(config) : {},
        autoStart,
      })
      onClose()
    } catch (error) {
      console.error("Failed to create node:", error)
      // Keep dialog open on error
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
      className="relative w-[500px]"
      style={
        isAppleGlass
          ? {
              background: 'var(--glass-background)',
              backdropFilter: 'var(--backdrop-blur)',
              WebkitBackdropFilter: 'var(--backdrop-blur)',
              border: `var(--border-width) solid var(--glass-border)`,
              borderRadius: 'var(--border-radius-xl)',
              boxShadow: `
                var(--shadow-glass),
                var(--shadow-glassInset),
                0 8px 48px rgba(99, 102, 241, 0.15)
              `,
            }
          : {
              background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95))',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              border: '1px solid rgba(34, 211, 238, 0.5)',
              borderRadius: '24px',
              boxShadow: '0 0 50px rgba(34, 211, 238, 0.4)',
            }
      }
    >
      {/* Animated border glow (Cyberpunk only) */}
      {!isAppleGlass && (
        <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />
      )}

      {/* Header */}
      <div
        className="relative z-10 flex items-center justify-between p-5"
        style={
          isAppleGlass
            ? {
                background: 'rgba(255, 255, 255, 0.02)',
                borderBottom: `0.5px solid var(--glass-border)`,
              }
            : {
                background: 'rgba(15, 23, 42, 0.5)',
                borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
              }
        }
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center"
            style={
              isAppleGlass
                ? {
                    background: 'rgba(59, 130, 246, 0.15)',
                    border: '0.5px solid rgba(59, 130, 246, 0.4)',
                    backdropFilter: 'blur(8px)',
                    borderRadius: '12px',
                    boxShadow: 'var(--shadow-button)',
                  }
                : {
                    background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
                    borderRadius: '12px',
                    boxShadow: '0 0 20px rgba(34, 211, 238, 0.5)',
                  }
            }
          >
            <Plus className="h-5 w-5" style={{ color: isAppleGlass ? '#3b82f6' : '#ffffff' }} />
          </div>
          <div>
            <h2
              className="font-mono text-lg font-bold"
              style={
                isAppleGlass && textScrimTokens
                  ? {
                      color: 'var(--color-primary)',
                      background: textScrimTokens.title.background,
                      backdropFilter: textScrimTokens.title.backdropFilter,
                      border: textScrimTokens.title.border,
                      borderRadius: textScrimTokens.title.borderRadius,
                      padding: textScrimTokens.title.padding,
                      display: 'inline-block',
                    }
                  : {
                      color: '#22d3ee',
                    }
              }
            >
              Create Node
            </h2>
            <p
              className="text-xs mt-1"
              style={
                isAppleGlass && textScrimTokens
                  ? {
                      color: 'var(--color-text-secondary)',
                      background: textScrimTokens.subtitle.background,
                      backdropFilter: textScrimTokens.subtitle.backdropFilter,
                      border: textScrimTokens.subtitle.border,
                      borderRadius: textScrimTokens.subtitle.borderRadius,
                      padding: textScrimTokens.subtitle.padding,
                      display: 'inline-block',
                    }
                  : {
                      color: '#94a3b8',
                    }
              }
            >
              Add new node to the mesh
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="group rounded-xl p-2 transition-all cursor-pointer"
          style={
            isAppleGlass
              ? {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '0.5px solid var(--glass-border)',
                  backdropFilter: 'blur(8px)',
                }
              : {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }
          }
          onMouseEnter={(e) => {
            if (isAppleGlass) {
              e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'
              e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.4)'
            } else {
              e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'
              e.currentTarget.style.borderColor = 'rgba(248, 113, 113, 0.5)'
            }
          }}
          onMouseLeave={(e) => {
            if (isAppleGlass) {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
              e.currentTarget.style.borderColor = 'var(--glass-border)'
            } else {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'
            }
          }}
        >
          <X
            className="h-5 w-5 transition-colors group-hover:text-red-300"
            style={{ color: isAppleGlass ? 'var(--color-text-secondary)' : '#94a3b8' }}
          />
        </button>
      </div>

      {/* Form */}
      <div className="relative z-10 space-y-5 p-6 max-h-[60vh] overflow-y-auto cyberpunk-scrollbar">
        {/* Node ID Input */}
        <div className="space-y-2">
          <label
            className="block text-sm font-medium"
            style={{ color: isAppleGlass ? 'var(--color-primary)' : '#cbd5e1' }}
          >
            Node ID
          </label>
          <input
            type="text"
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
            placeholder="e.g., my-new-node"
            className="w-full font-mono text-sm px-4 py-3 focus:outline-none transition-all"
            style={
              isAppleGlass
                ? {
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '0.5px solid var(--glass-border)',
                    borderRadius: '12px',
                    backdropFilter: 'blur(8px)',
                    color: 'var(--color-primary)',
                  }
                : {
                    background: 'rgba(30, 41, 59, 0.5)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '12px',
                    backdropFilter: 'blur(16px)',
                    color: '#ffffff',
                  }
            }
            onFocus={(e) => {
              if (isAppleGlass) {
                e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.4)'
                e.currentTarget.style.boxShadow = '0 0 0 2px rgba(59, 130, 246, 0.1)'
              } else {
                e.currentTarget.style.borderColor = 'rgba(34, 211, 238, 0.5)'
                e.currentTarget.style.boxShadow = '0 0 0 2px rgba(34, 211, 238, 0.2)'
              }
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = isAppleGlass ? 'var(--glass-border)' : 'rgba(255, 255, 255, 0.2)'
              e.currentTarget.style.boxShadow = 'none'
            }}
            autoFocus
          />
        </div>

        {/* Node Type Selection */}
        <div className="space-y-2">
          <label
            className="block text-sm font-medium"
            style={{ color: isAppleGlass ? 'var(--color-primary)' : '#cbd5e1' }}
          >
            Node Type
          </label>
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
                  className="relative flex items-center gap-3 p-4 transition-all cursor-pointer"
                  style={
                    isSelected
                      ? isAppleGlass
                        ? {
                            background: 'rgba(59, 130, 246, 0.15)',
                            border: '0.5px solid rgba(59, 130, 246, 0.4)',
                            borderRadius: '12px',
                            backdropFilter: 'blur(8px)',
                            boxShadow: 'var(--shadow-button)',
                          }
                        : {
                            background: 'rgba(6, 182, 212, 0.2)',
                            border: '1px solid rgba(34, 211, 238, 0.5)',
                            borderRadius: '12px',
                            boxShadow: '0 0 20px rgba(34, 211, 238, 0.2)',
                          }
                      : isAppleGlass
                      ? {
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '0.5px solid var(--glass-border)',
                          borderRadius: '12px',
                          backdropFilter: 'blur(8px)',
                        }
                      : {
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          borderRadius: '12px',
                        }
                  }
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      if (isAppleGlass) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.7)'
                      } else {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)'
                      }
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      if (isAppleGlass) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                        e.currentTarget.style.borderColor = 'var(--glass-border)'
                      } else {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'
                      }
                    }
                  }}
                >
                  <Icon
                    className="h-5 w-5"
                    style={{
                      color: isSelected
                        ? isAppleGlass
                          ? '#3b82f6'
                          : '#22d3ee'
                        : isAppleGlass
                        ? 'var(--color-text-secondary)'
                        : '#94a3b8',
                    }}
                  />
                  <span
                    className="text-sm font-medium"
                    style={{
                      color: isSelected
                        ? isAppleGlass
                          ? '#3b82f6'
                          : '#22d3ee'
                        : isAppleGlass
                        ? 'var(--color-primary)'
                        : '#cbd5e1',
                    }}
                  >
                    {type.label}
                  </span>
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute right-3 top-1/2 -translate-y-1/2"
                    >
                      <Check
                        className="h-4 w-4"
                        style={{ color: isAppleGlass ? '#3b82f6' : '#22d3ee' }}
                      />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <label
            className="block text-sm font-medium"
            style={{ color: isAppleGlass ? 'var(--color-primary)' : '#cbd5e1' }}
          >
            Description (Optional)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the purpose of this node..."
            maxLength={1000}
            rows={3}
            className="w-full text-sm px-4 py-3 focus:outline-none transition-all resize-none cyberpunk-scrollbar-thin"
            style={
              isAppleGlass
                ? {
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '0.5px solid var(--glass-border)',
                    borderRadius: '12px',
                    backdropFilter: 'blur(8px)',
                    color: 'var(--color-primary)',
                  }
                : {
                    background: 'rgba(30, 41, 59, 0.5)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '12px',
                    backdropFilter: 'blur(16px)',
                    color: '#ffffff',
                  }
            }
            onFocus={(e) => {
              if (isAppleGlass) {
                e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.4)'
                e.currentTarget.style.boxShadow = '0 0 0 2px rgba(59, 130, 246, 0.1)'
              } else {
                e.currentTarget.style.borderColor = 'rgba(34, 211, 238, 0.5)'
                e.currentTarget.style.boxShadow = '0 0 0 2px rgba(34, 211, 238, 0.2)'
              }
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = isAppleGlass ? 'var(--glass-border)' : 'rgba(255, 255, 255, 0.2)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          />
          <div
            className="text-xs text-right"
            style={{ color: isAppleGlass ? 'var(--color-text-muted)' : '#64748b' }}
          >
            {description.length}/1000
          </div>
        </div>

        {/* JSON Config */}
        <div className="space-y-2">
          <label
            className="block text-sm font-medium"
            style={{ color: isAppleGlass ? 'var(--color-primary)' : '#cbd5e1' }}
          >
            Configuration (JSON)
          </label>
          <textarea
            value={config}
            onChange={(e) => {
              setConfig(e.target.value)
              setConfigError(null)
            }}
            placeholder='{"key": "value"}'
            rows={6}
            className="w-full font-mono text-sm px-4 py-3 focus:outline-none transition-all resize-none cyberpunk-scrollbar-thin"
            style={
              configError
                ? {
                    background: isAppleGlass ? 'rgba(255, 255, 255, 0.05)' : 'rgba(30, 41, 59, 0.5)',
                    border: isAppleGlass ? '0.5px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(248, 113, 113, 0.5)',
                    borderRadius: '12px',
                    backdropFilter: isAppleGlass ? 'blur(8px)' : 'blur(16px)',
                    color: isAppleGlass ? 'var(--color-primary)' : '#ffffff',
                  }
                : isAppleGlass
                ? {
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '0.5px solid var(--glass-border)',
                    borderRadius: '12px',
                    backdropFilter: 'blur(8px)',
                    color: 'var(--color-primary)',
                  }
                : {
                    background: 'rgba(30, 41, 59, 0.5)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '12px',
                    backdropFilter: 'blur(16px)',
                    color: '#ffffff',
                  }
            }
            onFocus={(e) => {
              if (!configError) {
                if (isAppleGlass) {
                  e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.4)'
                  e.currentTarget.style.boxShadow = '0 0 0 2px rgba(59, 130, 246, 0.1)'
                } else {
                  e.currentTarget.style.borderColor = 'rgba(34, 211, 238, 0.5)'
                  e.currentTarget.style.boxShadow = '0 0 0 2px rgba(34, 211, 238, 0.2)'
                }
              }
            }}
            onBlur={(e) => {
              if (!configError) {
                e.currentTarget.style.borderColor = isAppleGlass ? 'var(--glass-border)' : 'rgba(255, 255, 255, 0.2)'
                e.currentTarget.style.boxShadow = 'none'
              }
            }}
          />
          {configError && (
            <div
              className="text-xs flex items-center gap-1"
              style={{ color: isAppleGlass ? '#ef4444' : '#f87171' }}
            >
              <span
                className="inline-block w-1 h-1 rounded-full"
                style={{ background: isAppleGlass ? '#ef4444' : '#f87171' }}
              />
              {configError}
            </div>
          )}
          <div
            className="text-xs"
            style={{ color: isAppleGlass ? 'var(--color-text-muted)' : '#64748b' }}
          >
            Enter valid JSON configuration for the node
          </div>
        </div>

        {/* Auto Start Toggle */}
        <div
          className="flex items-center justify-between p-4"
          style={
            isAppleGlass
              ? {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '0.5px solid var(--glass-border)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(8px)',
                }
              : {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '12px',
                }
          }
        >
          <div>
            <div
              className="text-sm font-medium"
              style={{ color: isAppleGlass ? 'var(--color-primary)' : '#cbd5e1' }}
            >
              Auto Start
            </div>
            <div
              className="text-xs"
              style={{ color: isAppleGlass ? 'var(--color-text-secondary)' : '#94a3b8' }}
            >
              Start node automatically after creation
            </div>
          </div>
          <button
            onClick={() => setAutoStart(!autoStart)}
            className="relative h-7 w-12 rounded-full transition-all cursor-pointer"
            style={{
              background: autoStart
                ? isAppleGlass
                  ? '#3b82f6'
                  : '#06b6d4'
                : isAppleGlass
                ? 'var(--color-text-muted)'
                : '#475569',
            }}
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
      <div
        className="relative z-10 flex gap-3 p-5"
        style={
          isAppleGlass
            ? {
                background: 'rgba(255, 255, 255, 0.02)',
                borderTop: `0.5px solid var(--glass-border)`,
              }
            : {
                background: 'rgba(15, 23, 42, 0.5)',
                borderTop: '1px solid rgba(255, 255, 255, 0.1)',
              }
        }
      >
        <button
          onClick={onClose}
          disabled={creating}
          className="flex-1 rounded-xl py-3 text-sm font-medium transition-all"
          style={
            isAppleGlass
              ? {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '0.5px solid var(--glass-border)',
                  backdropFilter: 'blur(8px)',
                  color: 'var(--color-text-secondary)',
                  opacity: creating ? 0.5 : 1,
                  cursor: creating ? 'not-allowed' : 'pointer',
                }
              : {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#cbd5e1',
                  opacity: creating ? 0.5 : 1,
                  cursor: creating ? 'not-allowed' : 'pointer',
                }
          }
          onMouseEnter={(e) => {
            if (!creating) {
              e.currentTarget.style.background = isAppleGlass
                ? 'rgba(255, 255, 255, 0.1)'
                : 'rgba(255, 255, 255, 0.1)'
            }
          }}
          onMouseLeave={(e) => {
            if (!creating) {
              e.currentTarget.style.background = isAppleGlass
                ? 'rgba(255, 255, 255, 0.05)'
                : 'rgba(255, 255, 255, 0.05)'
            }
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={!nodeId.trim() || creating}
          className="flex-1 rounded-xl py-3 text-sm font-medium transition-all flex items-center justify-center gap-2"
          style={
            nodeId.trim() && !creating
              ? isAppleGlass
                ? {
                    background: 'rgba(59, 130, 246, 0.15)',
                    border: '0.5px solid rgba(59, 130, 246, 0.4)',
                    backdropFilter: 'blur(8px)',
                    color: '#3b82f6',
                    cursor: 'pointer',
                  }
                : {
                    background: 'rgba(6, 182, 212, 0.2)',
                    border: '1px solid rgba(34, 211, 238, 0.5)',
                    color: '#22d3ee',
                    cursor: 'pointer',
                  }
              : isAppleGlass
              ? {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '0.5px solid var(--glass-border)',
                  color: 'var(--color-text-muted)',
                  cursor: 'not-allowed',
                  opacity: 0.5,
                }
              : {
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#64748b',
                  cursor: 'not-allowed',
                  opacity: 0.5,
                }
          }
          onMouseEnter={(e) => {
            if (nodeId.trim() && !creating) {
              if (isAppleGlass) {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)'
                e.currentTarget.style.boxShadow = 'var(--shadow-button)'
              } else {
                e.currentTarget.style.background = 'rgba(6, 182, 212, 0.3)'
                e.currentTarget.style.boxShadow = '0 0 20px rgba(34, 211, 238, 0.3)'
              }
            }
          }}
          onMouseLeave={(e) => {
            if (nodeId.trim() && !creating) {
              e.currentTarget.style.background = isAppleGlass
                ? 'rgba(59, 130, 246, 0.15)'
                : 'rgba(6, 182, 212, 0.2)'
              e.currentTarget.style.boxShadow = 'none'
            }
          }}
        >
          {creating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating...
            </>
          ) : (
            "Create Node"
          )}
        </button>
      </div>
    </motion.div>
  )
}
