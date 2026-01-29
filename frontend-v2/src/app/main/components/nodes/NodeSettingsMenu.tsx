/**
 * Node Settings Menu - Dropdown menu triggered by Settings button
 * Provides Edit and Delete actions for nodes
 */

import { ReactNode } from "react"
import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { Edit, Trash2 } from "lucide-react"

interface NodeSettingsMenuProps {
  nodeId: string
  onEdit: () => void
  onDelete: () => void
  children: ReactNode
}

export function NodeSettingsMenu({
  nodeId,
  onEdit,
  onDelete,
  children,
}: NodeSettingsMenuProps) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        {children}
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="z-[100] min-w-[180px] rounded-xl border border-cyan-400/20 bg-slate-900/95 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.2)] p-1.5"
          sideOffset={5}
          align="start"
          collisionPadding={10}
        >
          {/* Neon top accent */}
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />

          <DropdownMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
            onSelect={onEdit}
          >
            <Edit className="h-4 w-4" />
            <span>Edit Node</span>
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="my-1 h-px bg-slate-700/50" />

          <DropdownMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-red-500/20 hover:text-red-300 outline-none cursor-pointer transition-colors"
            onSelect={onDelete}
          >
            <Trash2 className="h-4 w-4" />
            <span>Delete Node</span>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
