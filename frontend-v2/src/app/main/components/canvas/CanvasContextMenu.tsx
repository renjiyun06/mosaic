/**
 * Canvas Context Menu - Right-click menu for canvas
 * Provides quick actions like creating nodes, connections, showing connections, and toggling topology
 */

import { ReactNode } from "react"
import * as ContextMenu from "@radix-ui/react-context-menu"
import { Plus, Network, Eye, EyeOff, Link } from "lucide-react"

interface CanvasContextMenuProps {
  children: ReactNode
  onCreateNode: () => void
  onCreateConnection: () => void
  onShowConnections: () => void
  showTopology: boolean
  onToggleTopology: () => void
}

export function CanvasContextMenu({
  children,
  onCreateNode,
  onCreateConnection,
  onShowConnections,
  showTopology,
  onToggleTopology,
}: CanvasContextMenuProps) {
  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        {children}
      </ContextMenu.Trigger>

      {/* Context Menu Portal */}
      <ContextMenu.Portal>
        <ContextMenu.Content
          className="min-w-[12rem] rounded-xl border border-cyan-400/20 bg-slate-900/95 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.2)] p-1.5 z-[100]"
          collisionPadding={10}
        >
          {/* Neon top accent */}
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
            onSelect={onCreateNode}
          >
            <Plus className="h-4 w-4" />
            Create Node
          </ContextMenu.Item>

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
            onSelect={onCreateConnection}
          >
            <Link className="h-4 w-4" />
            Create Connection
          </ContextMenu.Item>

          <ContextMenu.Separator className="my-1 h-px bg-slate-700/50" />

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
            onSelect={onShowConnections}
          >
            <Network className="h-4 w-4" />
            Show Connections
          </ContextMenu.Item>

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
            onSelect={onToggleTopology}
          >
            {showTopology ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            {showTopology ? "Hide Topology" : "Show Topology"}
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  )
}
