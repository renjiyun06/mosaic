/**
 * Close Session Dialog - Confirmation dialog for closing a session
 */

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import * as Dialog from "@radix-ui/react-dialog"
import { AlertTriangle, Loader2, X } from "lucide-react"

interface CloseSessionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessionId: string
  sessionTopic?: string
  onConfirm: () => Promise<void>
}

export function CloseSessionDialog({
  open,
  onOpenChange,
  sessionId,
  sessionTopic,
  onConfirm,
}: CloseSessionDialogProps) {
  const [isClosing, setIsClosing] = useState(false)

  const handleConfirm = async () => {
    setIsClosing(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to close session:", error)
    } finally {
      setIsClosing(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop */}
              <Dialog.Overlay asChild>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[150] bg-black/60 backdrop-blur-sm"
                />
              </Dialog.Overlay>

              {/* Dialog Content */}
              <Dialog.Content asChild>
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: 20 }}
                  transition={{ type: "spring", damping: 25, stiffness: 300 }}
                  className="fixed left-1/2 top-1/2 z-[200] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-red-500/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_50px_rgba(239,68,68,0.3)] backdrop-blur-xl"
                >
                  {/* Red top accent */}
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-red-500/50 to-transparent" />

                  {/* Close button */}
                  <Dialog.Close className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 transition-colors hover:bg-white/10 hover:text-slate-300">
                    <X className="h-4 w-4" />
                  </Dialog.Close>

                  <div className="p-6">
                    {/* Header */}
                    <div className="mb-4 flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-red-500/20 text-red-400">
                        <AlertTriangle className="h-6 w-6" />
                      </div>
                      <div>
                        <Dialog.Title className="text-lg font-semibold text-red-400">
                          Close Session?
                        </Dialog.Title>
                        <Dialog.Description className="text-sm text-slate-400">
                          This action cannot be undone
                        </Dialog.Description>
                      </div>
                    </div>

                    {/* Body */}
                    <div className="space-y-3">
                      <p className="text-sm text-slate-300">
                        Are you sure you want to close this session?
                      </p>

                      {/* Session Info */}
                      <div className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-3">
                        <div className="space-y-2">
                          {sessionTopic && (
                            <div>
                              <span className="text-xs text-slate-400">Topic:</span>
                              <p className="mt-0.5 text-sm font-medium text-cyan-300">
                                {sessionTopic}
                              </p>
                            </div>
                          )}
                          <div>
                            <span className="text-xs text-slate-400">Session ID:</span>
                            <p className="mt-0.5 font-mono text-xs text-slate-300">
                              {sessionId}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Warning */}
                      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3">
                        <div className="flex items-start gap-2 text-sm text-red-300">
                          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                          <p>
                            Once closed, this session will no longer accept new interactions.
                            All chat history will be preserved but read-only.
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="mt-6 flex gap-3">
                      <button
                        onClick={() => onOpenChange(false)}
                        disabled={isClosing}
                        className="flex-1 rounded-xl bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleConfirm}
                        disabled={isClosing}
                        className="flex-1 rounded-xl border border-red-500/50 bg-red-500/20 px-4 py-2.5 text-sm font-medium text-red-300 transition-all hover:bg-red-500/30 hover:shadow-[0_0_20px_rgba(239,68,68,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isClosing ? (
                          <span className="flex items-center justify-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Closing...
                          </span>
                        ) : (
                          "Close Session"
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
