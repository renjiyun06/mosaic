/**
 * Edge Context Menu - Right-click menu for connection edges
 */

import { useEffect, useState } from "react"
import * as ContextMenu from "@radix-ui/react-context-menu"
import { Bell, Plus, Edit, Trash2 } from "lucide-react"

interface EdgeContextMenuProps {
  edgeId: string
  sourceNodeId: string
  targetNodeId: string
  subscriptionCount: number
  onViewSubscriptions: () => void
  onAddSubscription: () => void
  onEditConnection: () => void
  onDeleteConnection: () => void
  children: React.ReactNode
}

export function EdgeContextMenu({
  edgeId,
  sourceNodeId,
  targetNodeId,
  subscriptionCount,
  onViewSubscriptions,
  onAddSubscription,
  onEditConnection,
  onDeleteConnection,
  children,
}: EdgeContextMenuProps) {
  const [open, setOpen] = useState(false)

  // Prevent default browser context menu
  useEffect(() => {
    const handleContextMenu = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (target.closest(`[data-edge-id="${edgeId}"]`)) {
        e.preventDefault()
      }
    }

    document.addEventListener("contextmenu", handleContextMenu)
    return () => document.removeEventListener("contextmenu", handleContextMenu)
  }, [edgeId])

  return (
    <ContextMenu.Root open={open} onOpenChange={setOpen}>
      <ContextMenu.Trigger asChild>
        {children}
      </ContextMenu.Trigger>

      <ContextMenu.Portal>
        <ContextMenu.Content
          className="z-[200] min-w-[240px] overflow-hidden rounded-xl border border-white/20 bg-slate-900/90 shadow-[0_0_30px_rgba(0,0,0,0.5)] backdrop-blur-xl"
          collisionPadding={10}
        >
          {/* Neon top accent */}
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />

          {/* Connection Info Header */}
          <div className="border-b border-white/10 px-3 py-2">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="truncate font-mono text-cyan-300">{sourceNodeId}</span>
              <span className="text-slate-500">→</span>
              <span className="truncate font-mono text-cyan-300">{targetNodeId}</span>
            </div>
          </div>

          {/* Menu Items */}
          <div className="p-1.5">
            <ContextMenu.Item
              className="group relative flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 outline-none transition-colors hover:bg-cyan-500/20 hover:text-cyan-300"
              onSelect={onViewSubscriptions}
            >
              <Bell className="h-4 w-4" />
              <span className="flex-1">View Subscriptions</span>
              {subscriptionCount > 0 && (
                <span className="rounded-full bg-cyan-500/20 px-1.5 py-0.5 text-xs font-semibold text-cyan-300">
                  {subscriptionCount}
                </span>
              )}
            </ContextMenu.Item>

            <ContextMenu.Item
              className="group relative flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 outline-none transition-colors hover:bg-cyan-500/20 hover:text-cyan-300"
              onSelect={onAddSubscription}
            >
              <Plus className="h-4 w-4" />
              <span>Add Subscription</span>
            </ContextMenu.Item>

            <ContextMenu.Separator className="my-1.5 h-px bg-white/10" />

            <ContextMenu.Item
              className="group relative flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 outline-none transition-colors hover:bg-cyan-500/20 hover:text-cyan-300"
              onSelect={onEditConnection}
            >
              <Edit className="h-4 w-4" />
              <span>Edit Connection</span>
            </ContextMenu.Item>

            <ContextMenu.Item
              className="group relative flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-400 outline-none transition-colors hover:bg-red-500/20 hover:text-red-300"
              onSelect={onDeleteConnection}
            >
              <Trash2 className="h-4 w-4" />
              <span>Delete Connection</span>
            </ContextMenu.Item>
          </div>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  )
}
