/**
 * Connections Sidebar - Right sidebar showing connection details
 */

import { motion, AnimatePresence } from "framer-motion"
import { Link2, X, Network, ArrowRight } from "lucide-react"
import type { Node } from "@xyflow/react"
import type { NodeConnection } from "../../types"
import { getNodeName } from "../../utils"

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
            className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm"
          />

          {/* Sidebar */}
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 z-[101] h-screen w-96 border-l border-cyan-400/30 bg-slate-900/95 shadow-[0_0_50px_rgba(34,211,238,0.3)] backdrop-blur-xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(34,211,238,0.4)]">
                  <Link2 className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="font-mono text-lg font-bold text-white">Connections</h2>
                  <p className="text-xs text-slate-400">{connections.length} active links</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/20"
              >
                <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-cyan-300" />
              </button>
            </div>

            {/* Connection List */}
            <div className="h-[calc(100vh-88px)] overflow-y-auto p-6">
              <div className="space-y-3">
                {connections.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <Network className="mb-4 h-12 w-12 text-slate-500" />
                    <p className="text-sm text-slate-400">No connections</p>
                  </div>
                ) : (
                  connections.map((conn, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="group rounded-xl border border-white/10 bg-white/5 p-4 transition-all hover:border-cyan-400/30 hover:bg-white/10"
                    >
                      {/* From Node */}
                      <div className="mb-3 flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
                        <span className="font-mono text-sm font-medium text-white">{getNodeName(conn.from, nodes)}</span>
                      </div>

                      {/* Connection Arrow & Event Type */}
                      <div className="ml-4 flex items-center gap-3 border-l-2 border-cyan-400/30 pl-4">
                        <ArrowRight className="h-4 w-4 text-cyan-400" />
                        <div className="flex-1">
                          <div className="rounded-lg bg-cyan-500/20 px-2 py-1 text-xs font-mono font-medium text-cyan-300">
                            {conn.eventType}
                          </div>
                        </div>
                      </div>

                      {/* To Node */}
                      <div className="mt-3 flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
                        <span className="font-mono text-sm font-medium text-white">{getNodeName(conn.to, nodes)}</span>
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
