/**
 * Canvas Context Menu - Right-click menu for canvas
 * Provides quick actions like creating nodes, connections, and toggling topology
 */

import { ReactNode } from "react"
import * as ContextMenu from "@radix-ui/react-context-menu"
import { Plus, Eye, EyeOff, Link } from "lucide-react"
import { useTheme } from "../../hooks/useTheme"

interface CanvasContextMenuProps {
  children: ReactNode
  onCreateNode: () => void
  onCreateConnection: () => void
  showTopology: boolean
  onToggleTopology: () => void
}

export function CanvasContextMenu({
  children,
  onCreateNode,
  onCreateConnection,
  showTopology,
  onToggleTopology,
}: CanvasContextMenuProps) {
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        {children}
      </ContextMenu.Trigger>

      {/* Context Menu Portal */}
      <ContextMenu.Portal>
        <ContextMenu.Content
          className="min-w-[12rem] p-1.5 z-[100]"
          style={
            isAppleGlass
              ? {
                  background: 'var(--glass-background)', // 3% opacity
                  backdropFilter: 'var(--backdrop-blur)', // blur(5px)
                  WebkitBackdropFilter: 'var(--backdrop-blur)',
                  border: `0.5px solid var(--glass-border)`,
                  borderRadius: '12px',
                  boxShadow: `
                    var(--shadow-glass),
                    var(--shadow-glassInset)
                  `,
                }
              : {
                  background: 'rgba(15, 23, 42, 0.95)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  border: '1px solid rgba(34, 211, 238, 0.2)',
                  borderRadius: '12px',
                  boxShadow: '0 0 30px rgba(34, 211, 238, 0.2)',
                }
          }
          collisionPadding={10}
        >
          {/* Neon top accent (Cyberpunk only) */}
          {!isAppleGlass && (
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />
          )}

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm outline-none cursor-pointer transition-colors"
            style={
              isAppleGlass
                ? {
                    borderRadius: '8px',
                    color: 'var(--color-primary)',
                  }
                : {
                    borderRadius: '8px',
                    color: '#cbd5e1',
                  }
            }
            onSelect={onCreateNode}
            onMouseEnter={(e) => {
              if (isAppleGlass) {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                e.currentTarget.style.color = '#3b82f6'
              } else {
                e.currentTarget.style.background = 'rgba(6, 182, 212, 0.2)'
                e.currentTarget.style.color = '#22d3ee'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = isAppleGlass ? 'var(--color-primary)' : '#cbd5e1'
            }}
          >
            <Plus className="h-4 w-4" />
            Create Node
          </ContextMenu.Item>

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm outline-none cursor-pointer transition-colors"
            style={
              isAppleGlass
                ? {
                    borderRadius: '8px',
                    color: 'var(--color-primary)',
                  }
                : {
                    borderRadius: '8px',
                    color: '#cbd5e1',
                  }
            }
            onSelect={onCreateConnection}
            onMouseEnter={(e) => {
              if (isAppleGlass) {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                e.currentTarget.style.color = '#3b82f6'
              } else {
                e.currentTarget.style.background = 'rgba(6, 182, 212, 0.2)'
                e.currentTarget.style.color = '#22d3ee'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = isAppleGlass ? 'var(--color-primary)' : '#cbd5e1'
            }}
          >
            <Link className="h-4 w-4" />
            Create Connection
          </ContextMenu.Item>

          <ContextMenu.Separator
            className="my-1 h-px"
            style={{
              background: isAppleGlass ? 'var(--glass-border)' : 'rgba(51, 65, 85, 0.5)',
            }}
          />

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm outline-none cursor-pointer transition-colors"
            style={
              isAppleGlass
                ? {
                    borderRadius: '8px',
                    color: 'var(--color-primary)',
                  }
                : {
                    borderRadius: '8px',
                    color: '#cbd5e1',
                  }
            }
            onSelect={onToggleTopology}
            onMouseEnter={(e) => {
              if (isAppleGlass) {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                e.currentTarget.style.color = '#3b82f6'
              } else {
                e.currentTarget.style.background = 'rgba(6, 182, 212, 0.2)'
                e.currentTarget.style.color = '#22d3ee'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = isAppleGlass ? 'var(--color-primary)' : '#cbd5e1'
            }}
          >
            {showTopology ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            {showTopology ? "Hide Topology" : "Show Topology"}
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  )
}
