/**
 * Session Menu - Context menu (right-click) for session actions
 * Provides Close, Archive, and Copy Session ID actions
 */

import { ReactNode } from "react"
import * as ContextMenu from "@radix-ui/react-context-menu"
import { XCircle, Archive, Copy } from "lucide-react"
import { SessionStatus } from "@/lib/types"

interface SessionMenuProps {
  sessionId: string
  sessionStatus: SessionStatus
  onCloseSession: () => void
  onArchiveSession: () => void
  children: ReactNode
}

export function SessionMenu({
  sessionId,
  sessionStatus,
  onCloseSession,
  onArchiveSession,
  children,
}: SessionMenuProps) {
  const isActive = sessionStatus === SessionStatus.ACTIVE
  const isClosed = sessionStatus === SessionStatus.CLOSED

  const handleCopySessionId = async () => {
    try {
      await navigator.clipboard.writeText(sessionId)
      console.log('[SessionMenu] Copied session ID:', sessionId)
    } catch (err) {
      console.error('[SessionMenu] Failed to copy session ID:', err)
    }
  }

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        {children}
      </ContextMenu.Trigger>

      <ContextMenu.Portal>
        <ContextMenu.Content
          className="z-[100] min-w-[180px] rounded-xl border border-cyan-400/20 bg-slate-900/95 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.2)] p-1.5"
          collisionPadding={10}
        >
          {/* Neon top accent - Cyberpunk style */}
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />

          {/* Close Session - only show when ACTIVE */}
          {isActive && (
            <>
              <ContextMenu.Item
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-400 hover:bg-red-500/20 hover:text-red-300 outline-none cursor-pointer transition-colors"
                onSelect={onCloseSession}
              >
                <XCircle className="h-4 w-4" />
                <span>Close Session</span>
              </ContextMenu.Item>
              <ContextMenu.Separator className="my-1 h-px bg-slate-700/50" />
            </>
          )}

          {/* Archive Session - only show when CLOSED */}
          {isClosed && (
            <>
              <ContextMenu.Item
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
                onSelect={onArchiveSession}
              >
                <Archive className="h-4 w-4" />
                <span>Archive Session</span>
              </ContextMenu.Item>
              <ContextMenu.Separator className="my-1 h-px bg-slate-700/50" />
            </>
          )}

          {/* Copy Session ID - always show */}
          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 outline-none cursor-pointer transition-colors"
            onSelect={handleCopySessionId}
          >
            <Copy className="h-4 w-4" />
            <span>Copy Session ID</span>
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  )
}
