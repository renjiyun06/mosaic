/**
 * Mosaic Dialog - Create/Edit Mosaic instance dialog
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, Edit, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { MosaicOut } from "@/lib/types"

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
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
          />

          {/* Dialog */}
          <div className="fixed left-1/2 top-1/2 z-[101] -translate-x-1/2 -translate-y-1/2">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{ type: "spring", damping: 20, stiffness: 200 }}
              className="relative w-[500px] rounded-3xl border border-cyan-400/50 bg-gradient-to-br from-slate-900/95 to-slate-800/95 shadow-[0_0_50px_rgba(34,211,238,0.4)] backdrop-blur-2xl"
            >
              {/* Animated border glow */}
              <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

              {/* Header */}
              <div className="relative z-10 flex items-center justify-between border-b border-white/10 bg-slate-900/50 p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(34,211,238,0.5)]">
                    {mosaic ? <Edit className="h-5 w-5 text-white" /> : <Plus className="h-5 w-5 text-white" />}
                  </div>
                  <div>
                    <h2 className="font-mono text-lg font-bold text-cyan-300">
                      {mosaic ? "Edit Mosaic" : "Create Mosaic"}
                    </h2>
                    <p className="text-xs text-slate-400">
                      {mosaic ? "Update Mosaic instance" : "Create new event mesh workspace"}
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-red-400/50 hover:bg-red-500/20"
                >
                  <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-red-300" />
                </button>
              </div>

              {/* Form */}
              <div className="relative z-10 space-y-5 p-6">
                {/* Mosaic Name Input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-slate-300">Mosaic Name *</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Production, Development"
                    className="w-full rounded-xl border border-white/20 bg-slate-800/50 px-4 py-3 font-mono text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl transition-all"
                    autoFocus
                    maxLength={100}
                  />
                </div>

                {/* Description Input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-slate-300">Description (Optional)</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe the purpose of this Mosaic instance..."
                    rows={3}
                    maxLength={500}
                    className="w-full rounded-xl border border-white/20 bg-slate-800/50 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl transition-all resize-none cyberpunk-scrollbar-thin"
                  />
                </div>
              </div>

              {/* Footer */}
              <div className="relative z-10 flex gap-3 border-t border-white/10 bg-slate-900/50 p-5">
                <button
                  onClick={onClose}
                  className="flex-1 rounded-xl border border-white/20 bg-white/5 py-3 text-sm font-medium text-slate-300 transition-all hover:bg-white/10"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!name.trim()}
                  className={cn(
                    "flex-1 rounded-xl border py-3 text-sm font-medium transition-all",
                    name.trim()
                      ? "border-cyan-400/50 bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 hover:shadow-[0_0_20px_rgba(34,211,238,0.3)] cursor-pointer"
                      : "border-white/10 bg-white/5 text-slate-500 cursor-not-allowed"
                  )}
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
