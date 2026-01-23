/**
 * Mosaic Sidebar - Left sidebar for switching between Mosaic instances
 */

import { motion } from "framer-motion"
import { useState, useRef, useEffect } from "react"
import * as ContextMenu from "@radix-ui/react-context-menu"
import * as Tooltip from "@radix-ui/react-tooltip"
import {
  Plus,
  Circle,
  Edit,
  Trash2,
  Play,
  Square,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { MosaicOut } from "@/lib/types"

interface MosaicSidebarProps {
  mosaics: MosaicOut[]
  currentMosaicId: number | null
  onSwitch: (id: number) => void
  onCreateNew: () => void
  onEdit: (mosaic: MosaicOut) => void
  onDelete: (mosaic: MosaicOut) => void
  onToggleStatus: (mosaic: MosaicOut) => void
}

export function MosaicSidebar({
  mosaics,
  currentMosaicId,
  onSwitch,
  onCreateNew,
  onEdit,
  onDelete,
  onToggleStatus,
}: MosaicSidebarProps) {
  // Track which mosaic has an open context menu
  const [contextMenuOpenFor, setContextMenuOpenFor] = useState<number | null>(null)
  // Track which mosaic should have tooltip disabled (after menu closes)
  const [tooltipDisabledFor, setTooltipDisabledFor] = useState<number | null>(null)
  const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const handleContextMenuChange = (mosaicId: number, open: boolean) => {
    setContextMenuOpenFor(open ? mosaicId : null)

    if (!open) {
      // Clear any existing timeout
      if (tooltipTimeoutRef.current) {
        clearTimeout(tooltipTimeoutRef.current)
      }

      // When menu closes, disable tooltip for a short time
      setTooltipDisabledFor(mosaicId)
      tooltipTimeoutRef.current = setTimeout(() => {
        setTooltipDisabledFor(null)
        tooltipTimeoutRef.current = null
      }, 500) // 500ms delay before tooltip can show again
    }
  }

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (tooltipTimeoutRef.current) {
        clearTimeout(tooltipTimeoutRef.current)
      }
    }
  }, [])

  return (
    <Tooltip.Provider delayDuration={300}>
      <div className="fixed left-0 top-0 bottom-0 w-16 bg-gradient-to-b from-slate-950/95 via-slate-950/90 to-cyan-950/85 backdrop-blur-xl border-r border-cyan-500/20 shadow-[2px_0_30px_rgba(34,211,238,0.1)] z-50">
      <div className="flex flex-col items-center py-4 space-y-3">
        {/* Logo / Mosaic Text */}
        <div className="py-2 relative">
          <span className="font-mono font-bold text-xs tracking-wider bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent [text-shadow:0_0_20px_rgba(34,211,238,0.8)] drop-shadow-[0_0_15px_rgba(34,211,238,0.6)] drop-shadow-[0_0_25px_rgba(34,211,238,0.4)]">
            MOSAIC
          </span>
        </div>

        <div className="w-12 h-px bg-slate-800" />

        {/* Mosaic Instance List */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden space-y-3 py-2 px-2 cyberpunk-scrollbar-thin">
          {mosaics.map((mosaic) => (
            <div key={mosaic.id} className="relative group">
              {/* Mosaic Icon with Right-Click Context Menu and Tooltip */}
              <Tooltip.Root open={contextMenuOpenFor === mosaic.id || tooltipDisabledFor === mosaic.id ? false : undefined}>
                <ContextMenu.Root onOpenChange={(open) => handleContextMenuChange(mosaic.id, open)}>
                  <ContextMenu.Trigger asChild>
                    <Tooltip.Trigger asChild>
                      <motion.div
                        onClick={() => onSwitch(mosaic.id)}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className={cn(
                          "relative w-12 h-12 rounded-xl cursor-pointer transition-all flex items-center justify-center",
                          currentMosaicId === mosaic.id
                            ? "bg-cyan-500/20 border-2 border-cyan-500 shadow-[0_0_20px_rgba(34,211,238,0.3)]"
                            : "bg-slate-800/50 border-2 border-transparent hover:border-cyan-500/30 hover:bg-slate-800/80"
                        )}
                      >
                        {/* Mosaic First Letter */}
                        <span
                          className={cn(
                            "font-bold text-lg font-mono",
                            currentMosaicId === mosaic.id ? "text-cyan-400" : "text-slate-400 group-hover:text-cyan-300"
                          )}
                        >
                          {mosaic.name[0].toUpperCase()}
                        </span>

                        {/* Status Indicator */}
                        <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-slate-950 flex items-center justify-center bg-slate-900">
                          <Circle
                            className={cn(
                              "h-2 w-2 fill-current",
                              mosaic.status === "running" ? "text-green-400 animate-pulse" : "text-slate-600"
                            )}
                          />
                        </div>
                      </motion.div>
                    </Tooltip.Trigger>
                  </ContextMenu.Trigger>

                  {/* Context Menu Portal */}
                  <ContextMenu.Portal>
                    <ContextMenu.Content
                      className="min-w-[12rem] rounded-xl border border-cyan-400/20 bg-slate-900/95 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.2)] p-1.5 z-[100]"
                      collisionPadding={10}
                    >
                      {/* Neon top accent */}
                      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />
                      {mosaic.status === "running" ? (
                        <ContextMenu.Item
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-red-500/20 hover:text-red-300 outline-none cursor-pointer transition-colors"
                          onSelect={() => onToggleStatus(mosaic)}
                        >
                          <Square className="h-4 w-4" />
                          Stop
                        </ContextMenu.Item>
                      ) : (
                        <ContextMenu.Item
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-green-500/20 hover:text-green-300 outline-none cursor-pointer transition-colors"
                          onSelect={() => onToggleStatus(mosaic)}
                        >
                          <Play className="h-4 w-4" />
                          Start
                        </ContextMenu.Item>
                      )}

                      <ContextMenu.Item
                        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
                        onSelect={() => onEdit(mosaic)}
                      >
                        <Edit className="h-4 w-4" />
                        Edit
                      </ContextMenu.Item>

                      <ContextMenu.Item
                        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-red-500/20 hover:text-red-300 outline-none cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        onSelect={() => onDelete(mosaic)}
                        disabled={mosaic.node_count > 0}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </ContextMenu.Item>
                    </ContextMenu.Content>
                  </ContextMenu.Portal>
                </ContextMenu.Root>

                {/* Hover Tooltip */}
                <Tooltip.Portal>
                  <Tooltip.Content
                    side="right"
                    sideOffset={16}
                    className="rounded-xl border border-cyan-400/30 bg-slate-900/95 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.2)] px-3 py-2 z-[60]"
                  >
                    <div className="font-semibold text-sm text-cyan-300">{mosaic.name}</div>
                  </Tooltip.Content>
                </Tooltip.Portal>
              </Tooltip.Root>
            </div>
          ))}
        </div>

        <div className="w-12 h-px bg-slate-800" />

        {/* Create New Mosaic Button */}
        <motion.div
          onClick={onCreateNew}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="w-12 h-12 rounded-xl border-2 border-dashed border-slate-700 hover:border-cyan-500 cursor-pointer flex items-center justify-center transition-all group"
        >
          <Plus className="h-5 w-5 text-slate-600 group-hover:text-cyan-400 transition-colors" />
        </motion.div>
      </div>
    </div>
    </Tooltip.Provider>
  )
}
