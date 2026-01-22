/**
 * Top Right Actions - Quick action buttons in top-right corner
 * Provides shortcuts for creating nodes and opening command palette
 */

import { motion } from "framer-motion"
import { Panel } from "@xyflow/react"
import { Plus, Command as CommandIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface TopRightActionsProps {
  onCreateNode: () => void
  onOpenCommand: () => void
}

export function TopRightActions({ onCreateNode, onOpenCommand }: TopRightActionsProps) {
  const buttons = [
    {
      icon: Plus,
      label: "Create Node",
      onClick: onCreateNode,
      hotkey: "Right-click",
    },
    {
      icon: CommandIcon,
      label: "Command Palette",
      onClick: onOpenCommand,
      hotkey: "⌘K",
    },
  ]

  return (
    <Panel position="top-right" className="m-4">
      <motion.div
        initial={{ x: 20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        className="flex gap-2"
      >
        {buttons.map((button, i) => (
          <motion.button
            key={i}
            onClick={button.onClick}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={cn(
              "group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all cursor-pointer",
              "bg-slate-900/80 backdrop-blur-xl border border-white/20",
              "hover:bg-cyan-500/20 hover:border-cyan-400/30",
              "shadow-xl hover:shadow-[0_0_20px_rgba(34,211,238,0.3)]"
            )}
          >
            <button.icon className="h-5 w-5 text-slate-400 group-hover:text-cyan-400 transition-colors" />

            {/* Tooltip */}
            <div className="pointer-events-none absolute top-full mt-2 whitespace-nowrap rounded-lg bg-slate-800/95 backdrop-blur-xl px-3 py-2 text-xs opacity-0 shadow-xl transition-opacity group-hover:opacity-100 border border-cyan-400/20">
              <div className="font-medium text-cyan-300">{button.label}</div>
              <div className="text-slate-400 text-[10px] mt-0.5">{button.hotkey}</div>
            </div>
          </motion.button>
        ))}
      </motion.div>
    </Panel>
  )
}
