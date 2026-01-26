/**
 * Delete Node Dialog - Confirmation dialog for deleting a node
 */

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import * as Dialog from "@radix-ui/react-dialog"
import { AlertTriangle, Loader2, X } from "lucide-react"
import { useTheme } from "../../hooks/useTheme"

interface DeleteNodeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  nodeId: string
  nodeName?: string
  activeSessions?: number
  incomingConnections?: number
  outgoingConnections?: number
  onConfirm: () => Promise<void>
}

export function DeleteNodeDialog({
  open,
  onOpenChange,
  nodeId,
  nodeName,
  activeSessions = 0,
  incomingConnections = 0,
  outgoingConnections = 0,
  onConfirm,
}: DeleteNodeDialogProps) {
  const { theme } = useTheme()
  const [isDeleting, setIsDeleting] = useState(false)

  const hasWarnings = activeSessions > 0 || incomingConnections > 0 || outgoingConnections > 0

  const handleConfirm = async () => {
    setIsDeleting(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to delete node:", error)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop Overlay */}
              <Dialog.Overlay asChild>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[150]"
                  style={{
                    background: 'var(--backdrop-overlay-bg)',
                    backdropFilter: 'var(--backdrop-overlay-blur)',
                  }}
                />
              </Dialog.Overlay>

              {/* Dialog Content */}
              <Dialog.Content asChild>
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: 20 }}
                  transition={{ type: "spring", damping: 25, stiffness: 300 }}
                  className="fixed left-1/2 top-1/2 z-[200] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-3xl"
                  style={{
                    background: 'var(--glass-background)',
                    backdropFilter: 'var(--backdrop-blur)',
                    border: `var(--border-width) solid rgba(239, 68, 68, 0.5)`,
                    boxShadow: theme === 'cyberpunk'
                      ? '0 0 50px rgba(239, 68, 68, 0.3)'
                      : 'var(--shadow-glass), var(--shadow-glass-inset)',
                  }}
                >
                  {/* Warning Top Accent - Cyberpunk Only */}
                  {theme === 'cyberpunk' && (
                    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-red-500/50 to-transparent" />
                  )}

                  {/* Close button */}
                  <Dialog.Close
                    className="absolute right-4 top-4 rounded-lg p-1 transition-colors focus:outline-none focus:ring-2"
                    style={{
                      color: 'var(--color-text-muted)',
                    }}
                    onMouseEnter={(e: React.MouseEvent<HTMLButtonElement>) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'
                      e.currentTarget.style.color = 'var(--color-text-secondary)'
                    }}
                    onMouseLeave={(e: React.MouseEvent<HTMLButtonElement>) => {
                      e.currentTarget.style.background = 'transparent'
                      e.currentTarget.style.color = 'var(--color-text-muted)'
                    }}
                    onFocus={(e: React.MouseEvent<HTMLButtonElement>) => {
                      e.currentTarget.style.outline = '2px solid var(--color-accent)'
                      e.currentTarget.style.outlineOffset = '2px'
                    }}
                    onBlur={(e: React.MouseEvent<HTMLButtonElement>) => {
                      e.currentTarget.style.outline = 'none'
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Dialog.Close>

                  <div className="p-6">
                    {/* Header */}
                    <div className="mb-4 flex items-center gap-3">
                      <div
                        className="flex h-12 w-12 items-center justify-center rounded-xl"
                        style={{
                          background: 'rgba(239, 68, 68, 0.2)',
                          border: `var(--border-width) solid rgba(239, 68, 68, 0.5)`,
                          color: '#f87171',
                        }}
                      >
                        <AlertTriangle className="h-6 w-6" />
                      </div>
                      <div>
                        <Dialog.Title
                          className="inline-block rounded-lg px-2.5 py-1.5 text-lg font-semibold"
                          style={{
                            color: '#f87171',
                            background: theme === 'apple-glass' ? 'var(--text-scrim-title-bg)' : 'transparent',
                            backdropFilter: theme === 'apple-glass' ? 'var(--text-scrim-title-blur)' : 'none',
                            border: theme === 'apple-glass' ? 'var(--text-scrim-title-border)' : 'none',
                            borderRadius: theme === 'apple-glass' ? '10px' : '0',
                            padding: theme === 'apple-glass' ? '6px 10px' : '0',
                          }}
                        >
                          Delete Node?
                        </Dialog.Title>
                        <Dialog.Description
                          className="mt-1 inline-block rounded-lg px-2.5 py-1.5 text-sm"
                          style={{
                            color: 'var(--color-text-secondary)',
                            background: theme === 'apple-glass' ? 'var(--text-scrim-subtitle-bg)' : 'transparent',
                            backdropFilter: theme === 'apple-glass' ? 'var(--text-scrim-subtitle-blur)' : 'none',
                            border: theme === 'apple-glass' ? 'var(--text-scrim-subtitle-border)' : 'none',
                            borderRadius: theme === 'apple-glass' ? '8px' : '0',
                            padding: theme === 'apple-glass' ? '5px 10px' : '0',
                          }}
                        >
                          This action cannot be undone
                        </Dialog.Description>
                      </div>
                    </div>

                    {/* Body */}
                    <div className="space-y-3">
                      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                        Are you sure you want to delete{" "}
                        <span className="font-mono font-semibold" style={{ color: 'var(--color-accent)' }}>{nodeId}</span>
                        {nodeName && <span style={{ color: 'var(--color-text-muted)' }}> ({nodeName})</span>}?
                      </p>

                      {/* Warnings */}
                      {hasWarnings && (
                        <div
                          className="rounded-xl p-3"
                          style={{
                            border: `var(--border-width) solid rgba(239, 68, 68, 0.5)`,
                            background: 'rgba(239, 68, 68, 0.1)',
                            backdropFilter: 'var(--backdrop-blur)',
                          }}
                        >
                          <div className="mb-2 flex items-center gap-2 text-sm font-medium" style={{ color: '#f87171' }}>
                            <AlertTriangle className="h-4 w-4" />
                            <span>Warning: This node has:</span>
                          </div>
                          <ul className="ml-6 space-y-1 text-sm" style={{ color: '#fca5a5' }}>
                            {activeSessions > 0 && (
                              <li>
                                • {activeSessions} active session{activeSessions > 1 ? "s" : ""}
                              </li>
                            )}
                            {incomingConnections > 0 && (
                              <li>
                                • {incomingConnections} incoming connection
                                {incomingConnections > 1 ? "s" : ""}
                              </li>
                            )}
                            {outgoingConnections > 0 && (
                              <li>
                                • {outgoingConnections} outgoing connection
                                {outgoingConnections > 1 ? "s" : ""}
                              </li>
                            )}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="mt-6 flex gap-3">
                      <button
                        onClick={() => onOpenChange(false)}
                        disabled={isDeleting}
                        className="flex-1 rounded-xl px-4 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                          border: `var(--border-width) solid var(--glass-border)`,
                          background: 'var(--glass-background-light)',
                          color: 'var(--color-text-secondary)',
                        }}
                        onMouseEnter={(e) => {
                          if (!isDeleting) {
                            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)'
                          }
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
                        disabled={isDeleting}
                        className="flex-1 rounded-xl px-4 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                          border: `var(--border-width) solid rgba(239, 68, 68, 0.5)`,
                          background: 'rgba(239, 68, 68, 0.15)',
                          color: '#fca5a5',
                          boxShadow: theme === 'cyberpunk' ? '0 0 20px rgba(239, 68, 68, 0.3)' : 'none',
                        }}
                        onMouseEnter={(e) => {
                          if (!isDeleting) {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)'
                            if (theme === 'cyberpunk') {
                              e.currentTarget.style.boxShadow = '0 0 30px rgba(239, 68, 68, 0.5)'
                            }
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'
                          if (theme === 'cyberpunk') {
                            e.currentTarget.style.boxShadow = '0 0 20px rgba(239, 68, 68, 0.3)'
                          }
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.outline = '2px solid rgba(239, 68, 68, 0.8)'
                          e.currentTarget.style.outlineOffset = '2px'
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.outline = 'none'
                        }}
                      >
                        {isDeleting ? (
                          <span className="flex items-center justify-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Deleting...
                          </span>
                        ) : (
                          "Delete Node"
                        )}
                      </button>
                    </div>
                  </div>
                </motion.div>
              </Dialog.Content>
            </>
          )}
        </AnimatePresence>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
