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
import { useTheme } from "../../hooks/useTheme"
import { textScrimTokens } from "../../themes/apple-glass"

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
  // Theme detection
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

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
      <div
        className="fixed left-0 top-0 bottom-0 w-16 border-r z-50"
        style={{
          background: isAppleGlass
            ? 'var(--glass-background)'
            : 'linear-gradient(to bottom, rgba(2, 6, 23, 0.95), rgba(2, 6, 23, 0.90), rgba(8, 51, 68, 0.85))',
          backdropFilter: isAppleGlass ? 'var(--backdrop-blur)' : 'blur(24px)',
          borderColor: isAppleGlass ? 'var(--glass-border)' : 'rgba(34, 211, 238, 0.2)',
          boxShadow: isAppleGlass
            ? 'var(--shadow-glass)'
            : '2px 0 30px rgba(34, 211, 238, 0.1)',
        }}
      >
      <div className="flex flex-col items-center py-4 space-y-3">
        {/* Logo / Mosaic Text */}
        <div className="py-2 relative">
          <span
            className="font-mono font-bold text-xs tracking-wider"
            style={
              isAppleGlass
                ? {
                    color: 'var(--color-primary)',
                    background: textScrimTokens.title.background,
                    backdropFilter: textScrimTokens.title.backdropFilter,
                    border: textScrimTokens.title.border,
                    borderRadius: textScrimTokens.title.borderRadius,
                    padding: '4px 8px',
                    display: 'inline-block',
                  }
                : {
                    background: 'linear-gradient(to right, #22d3ee, #3b82f6, #a855f7)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    textShadow: '0 0 20px rgba(34, 211, 238, 0.8)',
                    filter:
                      'drop-shadow(0 0 15px rgba(34, 211, 238, 0.6)) drop-shadow(0 0 25px rgba(34, 211, 238, 0.4))',
                  }
            }
          >
            MOSAIC
          </span>
        </div>

        <div
          className="w-12 h-px"
          style={{
            background: isAppleGlass ? 'var(--glass-border)' : '#1e293b',
          }}
        />

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
                        className="relative w-12 h-12 rounded-xl cursor-pointer transition-all flex items-center justify-center"
                        style={
                          currentMosaicId === mosaic.id
                            ? isAppleGlass
                              ? {
                                  background: 'var(--glass-background-light)',
                                  backdropFilter: 'var(--backdrop-blur)',
                                  border: '1px solid var(--color-accent)',
                                  boxShadow: 'var(--shadow-button)',
                                }
                              : {
                                  background: 'rgba(34, 211, 238, 0.2)',
                                  border: '2px solid #22d3ee',
                                  boxShadow: '0 0 20px rgba(34, 211, 238, 0.3)',
                                }
                            : isAppleGlass
                              ? {
                                  background: 'rgba(255, 255, 255, 0.02)',
                                  backdropFilter: 'blur(4px)',
                                  border: '1px solid transparent',
                                }
                              : {
                                  background: 'rgba(30, 41, 59, 0.5)',
                                  border: '2px solid transparent',
                                }
                        }
                      >
                        {/* Mosaic First Letter */}
                        <span
                          className="font-bold text-lg font-mono transition-colors"
                          style={{
                            color:
                              currentMosaicId === mosaic.id
                                ? isAppleGlass
                                  ? 'var(--color-accent)'
                                  : '#22d3ee'
                                : isAppleGlass
                                  ? 'var(--color-text-secondary)'
                                  : '#94a3b8',
                          }}
                        >
                          {mosaic.name[0].toUpperCase()}
                        </span>

                        {/* Status Indicator */}
                        <div
                          className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center"
                          style={{
                            border: isAppleGlass
                              ? '1.5px solid var(--glass-border)'
                              : '2px solid #020617',
                            background: isAppleGlass
                              ? 'rgba(255, 255, 255, 0.8)'
                              : '#0f172a',
                          }}
                        >
                          <Circle
                            className={cn(
                              "h-2 w-2 fill-current",
                              mosaic.status === "running" ? "animate-pulse" : ""
                            )}
                            style={{
                              color:
                                mosaic.status === "running"
                                  ? 'var(--color-success)'
                                  : isAppleGlass
                                    ? 'var(--color-text-muted)'
                                    : '#475569',
                            }}
                          />
                        </div>
                      </motion.div>
                    </Tooltip.Trigger>
                  </ContextMenu.Trigger>

                  {/* Context Menu Portal */}
                  <ContextMenu.Portal>
                    <ContextMenu.Content
                      className="min-w-[12rem] rounded-xl p-1.5 z-[100]"
                      style={{
                        background: isAppleGlass
                          ? 'var(--glass-background)'
                          : 'rgba(15, 23, 42, 0.95)',
                        backdropFilter: isAppleGlass
                          ? 'var(--backdrop-blur)'
                          : 'blur(24px)',
                        border: isAppleGlass
                          ? '0.5px solid var(--glass-border)'
                          : '1px solid rgba(34, 211, 238, 0.2)',
                        boxShadow: isAppleGlass
                          ? 'var(--shadow-glass)'
                          : '0 0 30px rgba(34, 211, 238, 0.2)',
                      }}
                      collisionPadding={10}
                    >
                      {/* Top accent */}
                      <div
                        className="absolute inset-x-0 top-0 h-px"
                        style={{
                          background: isAppleGlass
                            ? 'linear-gradient(to right, transparent, rgba(255, 255, 255, 0.4), transparent)'
                            : 'linear-gradient(to right, transparent, rgba(34, 211, 238, 0.5), transparent)',
                        }}
                      />
                      {mosaic.status === "running" ? (
                        <ContextMenu.Item
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm outline-none cursor-pointer transition-colors"
                          style={{
                            color: isAppleGlass
                              ? 'var(--color-text-primary)'
                              : '#cbd5e1',
                          }}
                          onSelect={() => onToggleStatus(mosaic)}
                        >
                          <Square className="h-4 w-4" />
                          Stop
                        </ContextMenu.Item>
                      ) : (
                        <ContextMenu.Item
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm outline-none cursor-pointer transition-colors"
                          style={{
                            color: isAppleGlass
                              ? 'var(--color-text-primary)'
                              : '#cbd5e1',
                          }}
                          onSelect={() => onToggleStatus(mosaic)}
                        >
                          <Play className="h-4 w-4" />
                          Start
                        </ContextMenu.Item>
                      )}

                      <ContextMenu.Item
                        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm outline-none cursor-pointer transition-colors"
                        style={{
                          color: isAppleGlass
                            ? 'var(--color-text-primary)'
                            : '#cbd5e1',
                        }}
                        onSelect={() => onEdit(mosaic)}
                      >
                        <Edit className="h-4 w-4" />
                        Edit
                      </ContextMenu.Item>

                      <ContextMenu.Item
                        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm outline-none cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                          color: isAppleGlass
                            ? 'var(--color-text-primary)'
                            : '#cbd5e1',
                        }}
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
                    className="rounded-xl px-3 py-2 z-[60]"
                    style={{
                      background: isAppleGlass
                        ? 'var(--glass-background)'
                        : 'rgba(15, 23, 42, 0.95)',
                      backdropFilter: isAppleGlass
                        ? 'var(--backdrop-blur)'
                        : 'blur(24px)',
                      border: isAppleGlass
                        ? '0.5px solid var(--glass-border)'
                        : '1px solid rgba(34, 211, 238, 0.3)',
                      boxShadow: isAppleGlass
                        ? 'var(--shadow-glass)'
                        : '0 0 30px rgba(34, 211, 238, 0.2)',
                    }}
                  >
                    <div
                      className="font-semibold text-sm"
                      style={
                        isAppleGlass
                          ? {
                              color: 'var(--color-primary)',
                              background: textScrimTokens.subtitle.background,
                              backdropFilter: textScrimTokens.subtitle.backdropFilter,
                              border: textScrimTokens.subtitle.border,
                              borderRadius: textScrimTokens.subtitle.borderRadius,
                              padding: textScrimTokens.subtitle.padding,
                            }
                          : {
                              color: '#22d3ee',
                            }
                      }
                    >
                      {mosaic.name}
                    </div>
                  </Tooltip.Content>
                </Tooltip.Portal>
              </Tooltip.Root>
            </div>
          ))}
        </div>

        <div
          className="w-12 h-px"
          style={{
            background: isAppleGlass ? 'var(--glass-border)' : '#1e293b',
          }}
        />

        {/* Create New Mosaic Button */}
        <motion.div
          onClick={onCreateNew}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="w-12 h-12 rounded-xl border-2 border-dashed cursor-pointer flex items-center justify-center transition-all group"
          style={{
            borderColor: isAppleGlass
              ? 'var(--glass-border)'
              : '#334155',
          }}
        >
          <Plus
            className="h-5 w-5 transition-colors"
            style={{
              color: isAppleGlass
                ? 'var(--color-text-muted)'
                : '#475569',
            }}
          />
        </motion.div>
      </div>
    </div>
    </Tooltip.Provider>
  )
}
