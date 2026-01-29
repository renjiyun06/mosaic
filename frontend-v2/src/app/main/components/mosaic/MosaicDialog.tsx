/**
 * Mosaic Dialog - Create/Edit Mosaic instance dialog
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, Edit, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { MosaicOut } from "@/lib/types"
import { useTheme } from "../../hooks/useTheme"

interface MosaicDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (name: string, description: string) => void
  mosaic?: MosaicOut | null
}

export function MosaicDialog({
  open,
  onClose,
  onSubmit,
  mosaic,
}: MosaicDialogProps) {
  const { theme, themeTokens } = useTheme()
  const isAppleGlass = theme === 'apple-glass'
  const textScrimTokens = isAppleGlass ? themeTokens.textScrimTokens : null

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

  useEffect(() => {
    if (open) {
      setName(mosaic?.name || "")
      setDescription(mosaic?.description || "")
    }
  }, [open, mosaic])

  const handleSubmit = () => {
    if (name.trim()) {
      onSubmit(name, description)
      setName("")
      setDescription("")
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[100]"
            style={
              isAppleGlass
                ? {
                    background: 'rgba(15, 23, 42, 0.4)', // Slate-900 40% opacity
                    backdropFilter: 'blur(12px)',
                    WebkitBackdropFilter: 'blur(12px)',
                  }
                : {
                    background: 'rgba(0, 0, 0, 0.6)', // Dark 60% opacity
                    backdropFilter: 'blur(8px)',
                    WebkitBackdropFilter: 'blur(8px)',
                  }
            }
          />

          {/* Dialog */}
          <div className="fixed left-1/2 top-1/2 z-[101] -translate-x-1/2 -translate-y-1/2">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{ type: "spring", damping: 20, stiffness: 200 }}
              className="relative w-[500px]"
              style={
                isAppleGlass
                  ? {
                      background: 'var(--glass-background)', // 3% opacity
                      backdropFilter: 'var(--backdrop-blur)', // blur(5px)
                      WebkitBackdropFilter: 'var(--backdrop-blur)',
                      border: `var(--border-width) solid var(--glass-border)`,
                      borderRadius: 'var(--border-radius-xl)', // 24px
                      boxShadow: `
                        var(--shadow-glass),
                        var(--shadow-glassInset),
                        0 8px 48px rgba(99, 102, 241, 0.15)
                      `, // Enhanced shadow for dialog prominence
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
                        background: 'rgba(255, 255, 255, 0.02)', // Subtle glass
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
                            background: 'rgba(59, 130, 246, 0.15)', // Blue-500 15%
                            border: '0.5px solid rgba(59, 130, 246, 0.4)',
                            backdropFilter: 'blur(8px)',
                            borderRadius: '12px',
                            boxShadow: 'var(--shadow-button)',
                          }
                        : {
                            background: 'linear-gradient(135deg, #06b6d4, #3b82f6)', // Cyan-500 → Blue-500
                            borderRadius: '12px',
                            boxShadow: '0 0 20px rgba(34, 211, 238, 0.5)',
                          }
                    }
                  >
                    {mosaic ? (
                      <Edit className="h-5 w-5" style={{ color: isAppleGlass ? '#3b82f6' : '#ffffff' }} />
                    ) : (
                      <Plus className="h-5 w-5" style={{ color: isAppleGlass ? '#3b82f6' : '#ffffff' }} />
                    )}
                  </div>
                  <div>
                    <h2
                      className="font-mono text-lg font-bold"
                      style={
                        isAppleGlass && textScrimTokens
                          ? {
                              color: 'var(--color-primary)', // Slate-900
                              background: textScrimTokens.title.background,
                              backdropFilter: textScrimTokens.title.backdropFilter,
                              border: textScrimTokens.title.border,
                              borderRadius: textScrimTokens.title.borderRadius,
                              padding: textScrimTokens.title.padding,
                              display: 'inline-block',
                            }
                          : {
                              color: '#22d3ee', // Cyan-400
                            }
                      }
                    >
                      {mosaic ? "Edit Mosaic" : "Create Mosaic"}
                    </h2>
                    <p
                      className="text-xs mt-1"
                      style={
                        isAppleGlass && textScrimTokens
                          ? {
                              color: 'var(--color-text-secondary)', // Slate-600
                              background: textScrimTokens.subtitle.background,
                              backdropFilter: textScrimTokens.subtitle.backdropFilter,
                              border: textScrimTokens.subtitle.border,
                              borderRadius: textScrimTokens.subtitle.borderRadius,
                              padding: textScrimTokens.subtitle.padding,
                              display: 'inline-block',
                            }
                          : {
                              color: '#94a3b8', // Slate-400
                            }
                      }
                    >
                      {mosaic ? "Update Mosaic instance" : "Create new event mesh workspace"}
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
              <div className="relative z-10 space-y-5 p-6">
                {/* Mosaic Name Input */}
                <div className="space-y-2">
                  <label
                    className="block text-sm font-medium"
                    style={{ color: isAppleGlass ? 'var(--color-primary)' : '#cbd5e1' }}
                  >
                    Mosaic Name *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Production, Development"
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
                    maxLength={100}
                  />
                </div>

                {/* Description Input */}
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
                    placeholder="Describe the purpose of this Mosaic instance..."
                    rows={3}
                    maxLength={500}
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
                  className="flex-1 rounded-xl py-3 text-sm font-medium transition-all cursor-pointer"
                  style={
                    isAppleGlass
                      ? {
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '0.5px solid var(--glass-border)',
                          backdropFilter: 'blur(8px)',
                          color: 'var(--color-text-secondary)',
                        }
                      : {
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.2)',
                          color: '#cbd5e1',
                        }
                  }
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = isAppleGlass
                      ? 'rgba(255, 255, 255, 0.1)'
                      : 'rgba(255, 255, 255, 0.1)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isAppleGlass
                      ? 'rgba(255, 255, 255, 0.05)'
                      : 'rgba(255, 255, 255, 0.05)'
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!name.trim()}
                  className="flex-1 rounded-xl py-3 text-sm font-medium transition-all"
                  style={
                    name.trim()
                      ? isAppleGlass
                        ? {
                            background: 'rgba(59, 130, 246, 0.15)', // Blue-500 15%
                            border: '0.5px solid rgba(59, 130, 246, 0.4)',
                            backdropFilter: 'blur(8px)',
                            color: '#3b82f6', // Blue-500
                            cursor: 'pointer',
                          }
                        : {
                            background: 'rgba(6, 182, 212, 0.2)', // Cyan-500 20%
                            border: '1px solid rgba(34, 211, 238, 0.5)',
                            color: '#22d3ee', // Cyan-400
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
                    if (name.trim()) {
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
                    if (name.trim()) {
                      e.currentTarget.style.background = isAppleGlass
                        ? 'rgba(59, 130, 246, 0.15)'
                        : 'rgba(6, 182, 212, 0.2)'
                      e.currentTarget.style.boxShadow = 'none'
                    }
                  }}
                >
                  {mosaic ? "Save Changes" : "Create Mosaic"}
                </button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  )
}
