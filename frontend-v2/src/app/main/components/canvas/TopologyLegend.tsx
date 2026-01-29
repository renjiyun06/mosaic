/**
 * Topology Legend - Shows connection types and their colors
 */

import { motion } from "framer-motion"
import { Panel } from "@xyflow/react"
import { Network } from "lucide-react"
import { LEGEND_ITEMS } from "../../utils"

interface TopologyLegendProps {
  show: boolean
}

export function TopologyLegend({ show }: TopologyLegendProps) {
  if (!show) return null

  return (
    <Panel position="bottom-right" className="bottom-4 right-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 20 }}
        className="rounded-2xl border border-white/20 bg-slate-900/90 p-4 shadow-2xl backdrop-blur-xl"
      >
        <div className="mb-3 flex items-center gap-2">
          <Network className="h-4 w-4 text-cyan-400" />
          <h3 className="font-mono text-sm font-semibold text-white">Connection Types</h3>
        </div>
        <div className="space-y-2">
          {LEGEND_ITEMS.map((item) => (
            <div key={item.eventType} className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div
                  className="h-0.5 w-8 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <div
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
              </div>
              <span className="font-mono text-xs text-slate-300">{item.label}</span>
            </div>
          ))}
        </div>
      </motion.div>
    </Panel>
  )
}
