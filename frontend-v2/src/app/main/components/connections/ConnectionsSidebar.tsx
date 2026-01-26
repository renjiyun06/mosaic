/**
 * Connections Sidebar - Right sidebar showing connection details
 */

import { motion, AnimatePresence } from "framer-motion"
import { Link2, X, Network, ArrowRight } from "lucide-react"
import type { Node } from "@xyflow/react"
import type { NodeConnection } from "../../types"
import { getNodeName } from "../../utils"
import { useTheme } from "../../hooks/useTheme"
import { textScrimTokens } from "../../themes/apple-glass"

interface ConnectionsSidebarProps {
  open: boolean
  onClose: () => void
  connections: NodeConnection[]
  nodes: Node[]
}

export function ConnectionsSidebar({
  open,
  onClose,
  connections,
  nodes,
}: ConnectionsSidebarProps) {
  // Theme detection
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

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
            style={{
              background: isAppleGlass
                ? 'rgba(15, 23, 42, 0.3)'
                : 'rgba(0, 0, 0, 0.4)',
              backdropFilter: isAppleGlass ? 'blur(8px)' : 'blur(4px)',
            }}
          />

          {/* Sidebar */}
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 z-[101] h-screen w-96 border-l"
            style={{
              background: isAppleGlass
                ? 'var(--glass-background)'
                : 'rgba(15, 23, 42, 0.95)',
              backdropFilter: isAppleGlass
                ? 'var(--backdrop-blur)'
                : 'blur(24px)',
              borderColor: isAppleGlass
                ? 'var(--glass-border)'
                : 'rgba(34, 211, 238, 0.3)',
              boxShadow: isAppleGlass
                ? 'var(--shadow-glass)'
                : '0 0 50px rgba(34, 211, 238, 0.3)',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between border-b p-6"
              style={{
                borderColor: isAppleGlass
                  ? 'var(--glass-border)'
                  : 'rgba(255, 255, 255, 0.1)',
              }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{
                    background: isAppleGlass
                      ? 'var(--color-accent)'
                      : 'linear-gradient(135deg, #22d3ee, #3b82f6)',
                    boxShadow: isAppleGlass
                      ? 'var(--shadow-button)'
                      : '0 0 20px rgba(34, 211, 238, 0.4)',
                  }}
                >
                  <Link2 className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2
                    className="font-mono text-lg font-bold"
                    style={
                      isAppleGlass
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
                            color: '#ffffff',
                          }
                    }
                  >
                    Connections
                  </h2>
                  <p
                    className="text-xs mt-1"
                    style={
                      isAppleGlass
                        ? {
                            color: 'var(--color-text-secondary)',
                            background: textScrimTokens.subtitle.background,
                            backdropFilter: textScrimTokens.subtitle.backdropFilter,
                            border: textScrimTokens.subtitle.border,
                            borderRadius: textScrimTokens.subtitle.borderRadius,
                            padding: '3px 8px',
                            display: 'inline-block',
                          }
                        : {
                            color: '#94a3b8',
                          }
                    }
                  >
                    {connections.length} active links
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="group rounded-xl border p-2 transition-all"
                style={{
                  borderColor: isAppleGlass
                    ? 'var(--glass-border)'
                    : 'rgba(255, 255, 255, 0.1)',
                  background: isAppleGlass
                    ? 'rgba(255, 255, 255, 0.02)'
                    : 'rgba(255, 255, 255, 0.05)',
                }}
              >
                <X
                  className="h-5 w-5 transition-colors"
                  style={{
                    color: isAppleGlass
                      ? 'var(--color-text-secondary)'
                      : '#94a3b8',
                  }}
                />
              </button>
            </div>

            {/* Connection List */}
            <div className="h-[calc(100vh-88px)] overflow-y-auto p-6 cyberpunk-scrollbar">
              <div className="space-y-3">
                {connections.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <Network
                      className="mb-4 h-12 w-12"
                      style={{
                        color: isAppleGlass
                          ? 'var(--color-text-muted)'
                          : '#64748b',
                      }}
                    />
                    <p
                      className="text-sm"
                      style={{
                        color: isAppleGlass
                          ? 'var(--color-text-secondary)'
                          : '#94a3b8',
                      }}
                    >
                      No connections
                    </p>
                  </div>
                ) : (
                  connections.map((conn, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="group rounded-xl border p-4 transition-all"
                      style={{
                        background: isAppleGlass
                          ? 'rgba(255, 255, 255, 0.02)'
                          : 'rgba(255, 255, 255, 0.05)',
                        backdropFilter: isAppleGlass ? 'blur(4px)' : undefined,
                        borderColor: isAppleGlass
                          ? 'var(--glass-border)'
                          : 'rgba(255, 255, 255, 0.1)',
                      }}
                    >
                      {/* From Node */}
                      <div className="mb-3 flex items-center gap-2">
                        <div
                          className="h-2 w-2 rounded-full"
                          style={{
                            background: 'var(--color-success)',
                            boxShadow: isAppleGlass
                              ? 'none'
                              : '0 0 8px rgba(52, 211, 153, 0.6)',
                          }}
                        />
                        <span
                          className="font-mono text-sm font-medium"
                          style={
                            isAppleGlass
                              ? {
                                  color: 'var(--color-primary)',
                                  background: textScrimTokens.subtitle.background,
                                  backdropFilter: textScrimTokens.subtitle.backdropFilter,
                                  border: textScrimTokens.subtitle.border,
                                  borderRadius: textScrimTokens.subtitle.borderRadius,
                                  padding: '4px 8px',
                                }
                              : {
                                  color: '#ffffff',
                                }
                          }
                        >
                          {getNodeName(conn.from, nodes)}
                        </span>
                      </div>

                      {/* Connection Arrow & Event Type */}
                      <div
                        className="ml-4 flex items-center gap-3 border-l-2 pl-4"
                        style={{
                          borderColor: isAppleGlass
                            ? 'var(--glass-border)'
                            : 'rgba(34, 211, 238, 0.3)',
                        }}
                      >
                        <ArrowRight
                          className="h-4 w-4"
                          style={{
                            color: isAppleGlass
                              ? 'var(--color-accent)'
                              : '#22d3ee',
                          }}
                        />
                        <div className="flex-1">
                          <div
                            className="rounded-lg px-2 py-1 text-xs font-mono font-medium"
                            style={{
                              background: isAppleGlass
                                ? 'rgba(59, 130, 246, 0.15)'
                                : 'rgba(34, 211, 238, 0.2)',
                              color: isAppleGlass
                                ? 'var(--color-accent)'
                                : '#22d3ee',
                              backdropFilter: isAppleGlass ? 'blur(4px)' : undefined,
                              border: isAppleGlass
                                ? '0.5px solid rgba(59, 130, 246, 0.3)'
                                : undefined,
                            }}
                          >
                            {conn.eventType}
                          </div>
                        </div>
                      </div>

                      {/* To Node */}
                      <div className="mt-3 flex items-center gap-2">
                        <div
                          className="h-2 w-2 rounded-full"
                          style={{
                            background: 'var(--color-accent)',
                            boxShadow: isAppleGlass
                              ? 'none'
                              : '0 0 8px rgba(59, 130, 246, 0.6)',
                          }}
                        />
                        <span
                          className="font-mono text-sm font-medium"
                          style={
                            isAppleGlass
                              ? {
                                  color: 'var(--color-primary)',
                                  background: textScrimTokens.subtitle.background,
                                  backdropFilter: textScrimTokens.subtitle.backdropFilter,
                                  border: textScrimTokens.subtitle.border,
                                  borderRadius: textScrimTokens.subtitle.borderRadius,
                                  padding: '4px 8px',
                                }
                              : {
                                  color: '#ffffff',
                                }
                          }
                        >
                          {getNodeName(conn.to, nodes)}
                        </span>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
