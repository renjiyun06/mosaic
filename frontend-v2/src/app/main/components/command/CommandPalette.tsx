/**
 * Command Palette - Quick command launcher (Cmd+K)
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Command } from "cmdk"
import { Search, X, Plus, Network, Terminal } from "lucide-react"

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [search, setSearch] = useState("")

  useEffect(() => {
    if (open) {
      setSearch("")
    }
  }, [open])

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

          {/* Command Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            className="fixed left-1/2 top-32 z-[101] w-full max-w-2xl -translate-x-1/2"
          >
            <Command className="overflow-hidden rounded-2xl border border-cyan-400/30 bg-slate-900/95 shadow-[0_0_50px_rgba(34,211,238,0.3)] backdrop-blur-xl">
              <div className="flex items-center border-b border-white/10 px-4">
                <Search className="h-5 w-5 text-slate-400" />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  placeholder="Type a command or search..."
                  className="flex-1 border-none bg-transparent px-4 py-5 text-white placeholder:text-slate-500 focus:outline-none"
                />
                <button
                  onClick={onClose}
                  className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <Command.List className="max-h-96 overflow-y-auto p-2">
                <Command.Empty className="py-10 text-center text-sm text-slate-400">
                  No results found.
                </Command.Empty>

                <Command.Group heading="Actions" className="mb-2">
                  <div className="mb-2 px-2 text-xs font-semibold text-slate-500">ACTIONS</div>
                  {[
                    { icon: Plus, label: "Create Node", shortcut: "⌘N" },
                    { icon: Network, label: "Create Connection", shortcut: "⌘L" },
                    { icon: Terminal, label: "Open Terminal", shortcut: "⌘T" },
                  ].map((item, i) => (
                    <Command.Item
                      key={i}
                      className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm text-slate-300 transition-colors hover:bg-cyan-500/20 hover:text-cyan-300 data-[selected=true]:bg-cyan-500/20 data-[selected=true]:text-cyan-300"
                    >
                      <div className="flex items-center gap-3">
                        <item.icon className="h-4 w-4" />
                        <span>{item.label}</span>
                      </div>
                      <kbd className="rounded bg-slate-800 px-2 py-1 font-mono text-xs text-slate-400">
                        {item.shortcut}
                      </kbd>
                    </Command.Item>
                  ))}
                </Command.Group>

                <Command.Group heading="Nodes" className="mb-2">
                  <div className="mb-2 px-2 text-xs font-semibold text-slate-500">NODES</div>
                  {["mosaic-develop", "advanced-programmer", "deep-search", "deep-wiki"].map((node, i) => (
                    <Command.Item
                      key={i}
                      className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm text-slate-300 transition-colors hover:bg-cyan-500/20 hover:text-cyan-300 data-[selected=true]:bg-cyan-500/20 data-[selected=true]:text-cyan-300"
                    >
                      <div className="flex items-center gap-3">
                        <div className="h-2 w-2 rounded-full bg-emerald-400" />
                        <span className="font-mono">{node}</span>
                      </div>
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
