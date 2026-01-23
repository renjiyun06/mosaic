/**
 * Expanded Node Card - Node session management interface with workspace panel
 */

import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Minimize2,
  Plus,
  MessageSquare,
  Send,
  Settings,
  Bot,
  Circle,
  MoreVertical,
  ChevronRight,
  Coins,
  BarChart3,
  ArrowUp,
  ArrowDown,
  Code2,
  X,
  Loader2,
  Copy,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { type NodeProps } from "@xyflow/react"
import { apiClient } from "@/lib/api"
import { SessionStatus, RuntimeStatus, MessageType, type SessionOut, type MessageOut } from "@/lib/types"
import { NodeSettingsMenu } from "./NodeSettingsMenu"
import { MessageBubble } from "./MessageBubble"

// Parsed message type (JSON payload)
interface ParsedMessage extends MessageOut {
  contentParsed: any
}

// Circular progress component for context usage
const CircularProgress = ({ percentage }: { percentage: number }) => {
  const getColor = () => {
    if (percentage < 60) return "rgba(34, 211, 238, 0.6)" // cyan
    if (percentage < 85) return "rgba(234, 179, 8, 0.6)" // yellow
    return "rgba(239, 68, 68, 0.7)" // red
  }

  const color = getColor()
  const circumference = 2 * Math.PI * 6
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <svg className="h-3.5 w-3.5 -rotate-90" viewBox="0 0 16 16">
      <circle
        cx="8"
        cy="8"
        r="6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className="text-slate-700"
      />
      <circle
        cx="8"
        cy="8"
        r="6"
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
      />
    </svg>
  )
}

export function ExpandedNodeCard({ data, selected }: NodeProps) {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [inputMessage, setInputMessage] = useState("")
  const [workspaceExpanded, setWorkspaceExpanded] = useState(false)
  const topicTextRef = useRef<HTMLSpanElement>(null)
  const [scrollDistance, setScrollDistance] = useState(0)

  // Refs for scrollable containers
  const sessionListRef = useRef<HTMLDivElement>(null)
  const messageListRef = useRef<HTMLDivElement>(null)

  // API State
  const [sessions, setSessions] = useState<SessionOut[]>([])
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [messages, setMessages] = useState<ParsedMessage[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [collapsedMessages, setCollapsedMessages] = useState<Set<string>>(new Set())

  // Hardcoded code-server URL for testing
  const codeServerUrl = "http://192.168.1.5:20001/?folder=/home/ren/mosaic/users/1/1/1"

  // Get selected session
  const selectedSession = sessions.find((s) => s.session_id === selectedSessionId)

  // Manual scroll handler for inner containers
  const handleManualScroll = useCallback(
    (e: React.WheelEvent, containerRef: React.RefObject<HTMLDivElement>) => {
      // Only handle normal scroll (not Ctrl+scroll which should zoom)
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault() // Prevent default browser scroll
        e.stopPropagation() // Stop event from reaching ReactFlow

        if (containerRef.current) {
          const container = containerRef.current

          // Get scroll properties
          const { scrollTop, scrollHeight, clientHeight } = container
          const maxScroll = scrollHeight - clientHeight

          // Calculate scroll amount with multiplier for better feel
          // deltaY is typically ±100 for mouse wheel, ±3 for trackpad
          const isTrackpad = Math.abs(e.deltaY) < 50
          const multiplier = isTrackpad ? 1 : 0.5 // Slower for mouse wheel
          const scrollAmount = e.deltaY * multiplier

          // Calculate new scroll position with boundaries
          const newScrollTop = Math.max(0, Math.min(maxScroll, scrollTop + scrollAmount))

          // Apply smooth scrolling
          container.scrollTo({
            top: newScrollTop,
            behavior: 'auto' // Use 'auto' for immediate response, 'smooth' for animation
          })
        }
      }
      // If Ctrl/Cmd is pressed, let the event bubble up for canvas zoom
    },
    []
  )

  // Load sessions when component mounts
  useEffect(() => {
    loadSessions()
  }, [data.id, data.mosaicId])

  // Load messages when session changes
  useEffect(() => {
    if (selectedSessionId && data.mosaicId) {
      loadMessages(selectedSessionId)
    }
  }, [selectedSessionId, data.id, data.mosaicId])

  // Calculate scroll distance based on text width
  useEffect(() => {
    if (topicTextRef.current && selectedSession) {
      const textWidth = topicTextRef.current.scrollWidth
      const containerWidth = 256 // w-64 = 256px
      const needsScroll = textWidth > containerWidth

      if (needsScroll) {
        // Calculate how much we need to scroll to reveal all text
        const distance = textWidth - containerWidth + 32 // +32px for padding
        setScrollDistance(distance)
      } else {
        setScrollDistance(0)
      }
    }
  }, [selectedSession?.topic])

  // Load sessions for this node
  const loadSessions = async () => {
    if (!data.mosaicId) {
      console.warn('[ExpandedNodeCard] mosaicId not available')
      return
    }

    try {
      setLoadingSessions(true)
      const response = await apiClient.listSessions(data.mosaicId, undefined, {
        page: 1,
        page_size: 1000,
      })

      // Filter sessions for this node (active + closed only)
      const nodeSessions = response.items.filter(
        (s) =>
          s.node_id === data.id &&
          (s.status === SessionStatus.ACTIVE || s.status === SessionStatus.CLOSED)
      )

      // Sort by created_at (newest first)
      nodeSessions.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )

      setSessions(nodeSessions)
      console.log('[ExpandedNodeCard] Loaded sessions:', nodeSessions.length)
    } catch (error) {
      console.error('[ExpandedNodeCard] Failed to load sessions:', error)
    } finally {
      setLoadingSessions(false)
    }
  }

  // Toggle message collapse state
  const toggleCollapse = useCallback((messageId: string) => {
    setCollapsedMessages((prev) => {
      const next = new Set(prev)
      if (next.has(messageId)) {
        next.delete(messageId)
      } else {
        next.add(messageId)
      }
      return next
    })
  }, [])

  // Load messages for selected session
  const loadMessages = async (sessionId: string) => {
    if (!data.mosaicId) {
      console.warn('[ExpandedNodeCard] mosaicId not available')
      return
    }

    try {
      setLoadingMessages(true)
      const response = await apiClient.listMessages(data.mosaicId, {
        nodeId: data.id,
        sessionId,
        page: 1,
        pageSize: 9999,
      })

      // Parse JSON payload
      const parsed: ParsedMessage[] = response.items.map((msg) => ({
        ...msg,
        contentParsed:
          typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload,
      }))

      setMessages(parsed)

      // Auto-collapse: thinking, system, tool use/output, pre_compact
      const collapsibleIds = parsed
        .filter(
          (msg) =>
            msg.message_type === MessageType.ASSISTANT_THINKING ||
            msg.message_type === MessageType.SYSTEM_MESSAGE ||
            msg.message_type === MessageType.ASSISTANT_TOOL_USE ||
            msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT ||
            msg.message_type === MessageType.ASSISTANT_PRE_COMPACT
        )
        .map((msg) => msg.message_id)

      setCollapsedMessages(new Set(collapsibleIds))
      console.log('[ExpandedNodeCard] Loaded messages:', parsed.length)
    } catch (error) {
      console.error('[ExpandedNodeCard] Failed to load messages:', error)
    } finally {
      setLoadingMessages(false)
    }
  }

  const handleSendMessage = () => {
    if (inputMessage.trim() && selectedSession?.status === SessionStatus.ACTIVE) {
      console.log("Sending:", inputMessage)
      // TODO: Implement WebSocket message sending
      setInputMessage("")
    }
  }

  // Format token number with K suffix
  const formatTokens = (num: number) => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toString()
  }

  return (
    <div className="flex h-[600px]" style={{ transformOrigin: "center" }}>
      {/* Left: Chat Area (900px) */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", damping: 20, stiffness: 200 }}
        className={cn(
          "group relative flex h-[600px] w-[900px] flex-col overflow-hidden rounded-3xl backdrop-blur-2xl transition-all",
          // Conditional border: remove right border when workspace expanded
          workspaceExpanded ? "rounded-r-none border-2 border-r-0" : "border-2",
          selected
            ? "border-cyan-400/80 shadow-[0_0_40px_rgba(34,211,238,0.5)]"
            : "border-cyan-400/50 shadow-[0_0_30px_rgba(34,211,238,0.3)]",
          "bg-gradient-to-br from-slate-900/95 to-slate-800/95"
        )}
        onWheel={(e) => {
          // For Ctrl+scroll, let it bubble up to ReactFlow for zoom
          if (e.ctrlKey || e.metaKey) {
            return // Allow event to propagate for canvas zoom
          }

          // For normal scroll, prevent it from reaching ReactFlow
          e.stopPropagation()
          // Note: We don't preventDefault here, let the inner containers handle it
        }}
      >
      {/* Animated border glow */}
      <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

      {/* Header - Node Info */}
      <div className="relative z-10 flex items-center justify-between border-b border-cyan-400/20 bg-slate-900/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/20">
            <Bot className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="font-mono text-base font-bold text-cyan-300">{data.id}</h2>
            <p className="text-xs text-slate-400">Claude Code Node</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Node Status Badge */}
          <div
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium",
              data.status === "running"
                ? "bg-emerald-500/20 text-emerald-300"
                : "bg-slate-600/50 text-slate-400"
            )}
          >
            {data.status === "running" ? "RUNNING" : "STOPPED"}
          </div>

          {/* Workspace Toggle Button - UX Best Practice: clear icon + text */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              setWorkspaceExpanded(!workspaceExpanded)
            }}
            className={cn(
              "group flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-all duration-200",
              // Hover state: UX Best Practice - visual feedback
              "hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]",
              // Focus state: UX Best Practice - keyboard accessibility
              "focus:outline-none focus:ring-2 focus:ring-cyan-400/50",
              // Cursor: UX Best Practice
              "cursor-pointer",
              workspaceExpanded
                ? "border-cyan-400/50 bg-cyan-500/20 text-cyan-300"
                : "border-white/10 bg-white/5 text-slate-400 hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:text-cyan-300"
            )}
            aria-label={workspaceExpanded ? "Collapse workspace" : "Expand workspace"}
          >
            <Code2 className="h-4 w-4" />
            <span>{workspaceExpanded ? "Close Workspace" : "Open Workspace"}</span>
          </button>

          {/* Settings Button */}
          <NodeSettingsMenu
            nodeId={data.id}
            onEdit={() => data.onEdit?.()}
            onDelete={() => data.onDelete?.()}
          >
            <button
              onClick={(e) => e.stopPropagation()}
              className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
            >
              <Settings className="h-4 w-4 text-slate-400 transition-colors group-hover:text-cyan-300" />
            </button>
          </NodeSettingsMenu>

          {/* Minimize Button */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              data.onCollapse()
            }}
            className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
          >
            <Minimize2 className="h-4 w-4 text-slate-400 transition-colors group-hover:text-cyan-300" />
          </button>
        </div>
      </div>

      {/* Main content area */}
      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* Left: Session list */}
        <div className="w-60 border-r border-cyan-400/20 bg-slate-900/30 backdrop-blur-sm flex flex-col">
          {/* Session list scroll area */}
          <div
            ref={sessionListRef}
            className="flex-1 overflow-y-auto p-3 space-y-2 cyberpunk-scrollbar-thin"
            onWheel={(e) => handleManualScroll(e, sessionListRef)}
          >
            {loadingSessions ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Loader2 className="mb-2 h-8 w-8 animate-spin text-cyan-400" />
                <p className="text-xs text-slate-400">Loading sessions...</p>
              </div>
            ) : sessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <MessageSquare className="mb-2 h-8 w-8 text-slate-500" />
                <p className="text-xs text-slate-400">No sessions</p>
              </div>
            ) : (
              sessions.map((session) => {
                const isSelected = selectedSessionId === session.session_id
                const statusColor =
                  session.status === SessionStatus.ACTIVE
                    ? session.runtime_status === RuntimeStatus.BUSY
                      ? "fill-orange-400 text-orange-400"
                      : "fill-green-400 text-green-400"
                    : "fill-gray-400 text-gray-400"

                return (
                  <motion.div
                    key={session.session_id}
                    onClick={() => setSelectedSessionId(session.session_id)}
                    whileHover={{ x: 3 }}
                    className={cn(
                      "group cursor-pointer rounded-xl border p-2.5 transition-all",
                      isSelected
                        ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                        : "border-white/10 bg-white/5 hover:border-cyan-400/30 hover:bg-white/10"
                    )}
                  >
                    {/* Simplified: Status dot + Topic + Menu */}
                    <div className="flex items-center gap-2">
                      <Circle className={cn("h-2 w-2 shrink-0", statusColor)} />
                      <span
                        className={cn(
                          "flex-1 truncate text-xs font-medium",
                          isSelected ? "text-cyan-300" : "text-white"
                        )}
                        title={session.topic || session.session_id}
                      >
                        {session.topic || session.session_id.slice(0, 8)}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          console.log("Menu for", session.session_id)
                        }}
                        className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      >
                        <MoreVertical className="h-3.5 w-3.5 text-slate-400 hover:text-cyan-300" />
                      </button>
                    </div>
                  </motion.div>
                )
              })
            )}
          </div>

          {/* Create Session Button - Fixed at bottom */}
          <div className="border-t border-cyan-400/20 p-3">
            <button
              onClick={() => data.onCreateSession?.(data.id)}
              className="w-full rounded-xl border border-cyan-400/30 bg-cyan-500/20 py-2 text-xs font-medium text-cyan-300 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/30 hover:shadow-[0_0_12px_rgba(34,211,238,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={data.status !== "running"}
            >
              <Plus className="mx-auto h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Right: Chat interface */}
        <div className="flex flex-1 flex-col">
          {!selectedSession ? (
            /* Empty State */
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <ChevronRight className="mx-auto mb-3 h-10 w-10 text-cyan-400/30" />
                <p className="text-sm text-slate-400">Select a session to start chatting</p>
              </div>
            </div>
          ) : (
            <>
              {/* Session Status Bar - Top of message area */}
              <div className="flex items-center gap-3 border-b border-cyan-400/20 bg-slate-900/50 px-4 py-2.5 backdrop-blur-sm">
                {/* Left: Status indicator + Session topic */}
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  {/* Status dot with icon (Accessibility: color + icon) */}
                  <div className="relative flex h-full shrink-0 items-center">
                    {selectedSession.status === SessionStatus.ACTIVE ? (
                      selectedSession.runtime_status === RuntimeStatus.BUSY ? (
                        <div className="flex items-center gap-1.5">
                          <Circle className="h-2 w-2 fill-orange-400 text-orange-400" />
                          <span className="text-[10px] font-medium leading-none text-orange-400">BUSY</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <Circle className="h-2 w-2 fill-green-400 text-green-400 animate-pulse" />
                          <span className="text-[10px] font-medium leading-none text-green-400">ACTIVE</span>
                        </div>
                      )
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <Circle className="h-2 w-2 fill-gray-400 text-gray-400" />
                        <span className="text-[10px] font-medium leading-none text-gray-400">CLOSED</span>
                      </div>
                    )}
                  </div>

                  {/* Divider */}
                  <div className="h-4 w-px shrink-0 bg-cyan-400/20" />

                  {/* Session topic - fixed width with marquee animation on hover */}
                  <div
                    className="group/topic relative flex h-full w-64 items-center overflow-hidden"
                    style={
                      {
                        "--scroll-distance": `${scrollDistance}px`,
                      } as React.CSSProperties
                    }
                  >
                    <div className="marquee-container flex items-center">
                      <span
                        ref={topicTextRef}
                        className="whitespace-nowrap text-sm font-medium leading-none text-cyan-300 marquee-text transition-all group-hover/topic:drop-shadow-[0_0_8px_rgba(34,211,238,0.6)]"
                      >
                        {selectedSession.topic || selectedSession.session_id.slice(0, 8)}
                      </span>
                    </div>
                    {/* Gradient fade - hidden on hover */}
                    <div className="pointer-events-none absolute right-0 top-0 h-full w-12 bg-gradient-to-l from-slate-900/50 to-transparent group-hover/topic:opacity-0 transition-opacity duration-300" />
                  </div>
                </div>

                {/* Right: Compact stats */}
                <div className="flex shrink-0 items-center gap-2.5 text-[10px] text-slate-400">
                  {/* Model badge */}
                  <span className="rounded-md bg-purple-500/20 px-2 py-1 font-mono font-medium text-purple-300">
                    {selectedSession.model || 'sonnet'}
                  </span>

                  {/* Mode badge */}
                  <span className="rounded-md bg-blue-500/20 px-2 py-1 font-mono font-medium text-blue-300">
                    {selectedSession.mode}
                  </span>
                </div>
              </div>

              {/* Messages area */}
              <div
                ref={messageListRef}
                className="flex-1 space-y-3 overflow-y-auto p-4 cyberpunk-scrollbar-thin"
                onWheel={(e) => handleManualScroll(e, messageListRef)}
              >
                {loadingMessages ? (
                  <div className="flex h-full items-center justify-center text-center">
                    <div>
                      <Loader2 className="mx-auto mb-2 h-10 w-10 animate-spin text-cyan-400" />
                      <p className="text-xs text-slate-400">Loading messages...</p>
                    </div>
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-center text-slate-400">
                    <div>
                      <MessageSquare className="mx-auto mb-2 h-10 w-10 opacity-30" />
                      <p className="text-xs">Send a message to start the conversation</p>
                    </div>
                  </div>
                ) : (
                  messages.map((msg) => {
                    // Skip assistant_result messages (stats only)
                    if (msg.message_type === MessageType.ASSISTANT_RESULT) {
                      return null
                    }

                    return (
                      <MessageBubble
                        key={msg.message_id}
                        message={msg}
                        onToggleCollapse={toggleCollapse}
                        isCollapsed={collapsedMessages.has(msg.message_id)}
                      />
                    )
                  })
                )}
              </div>

              {/* Input area */}
              <div className="border-t border-cyan-400/20 bg-slate-900/50 p-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault()
                        handleSendMessage()
                      }
                    }}
                    placeholder={
                      selectedSession.status === SessionStatus.CLOSED
                        ? "Session closed, cannot send messages"
                        : data.status !== "running"
                        ? "Node not running"
                        : "Type your message... (Enter to send)"
                    }
                    disabled={
                      selectedSession.status === SessionStatus.CLOSED || data.status !== "running"
                    }
                    className="flex-1 rounded-xl border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={
                      !inputMessage.trim() ||
                      selectedSession.status === SessionStatus.CLOSED ||
                      data.status !== "running"
                    }
                    className="group rounded-xl border border-cyan-400/30 bg-cyan-500/20 px-4 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/30 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none"
                  >
                    <Send className="h-4 w-4 text-cyan-300" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      </motion.div>

      {/* Right: Workspace Panel (700px, slides in from right) */}
      <AnimatePresence>
        {workspaceExpanded && (
          <motion.div
            initial={{ x: 700, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 700, opacity: 0 }}
            transition={{
              // UX Best Practice: 300ms duration, ease-out for entering
              duration: 0.3,
              ease: [0.4, 0, 0.2, 1], // Tailwind's ease-out
              opacity: { duration: 0.2 },
            }}
            className={cn(
              "relative flex h-[600px] w-[700px] flex-col overflow-hidden rounded-3xl rounded-l-none backdrop-blur-2xl",
              // Seamless border connection: no left border
              "border-2 border-l-0",
              selected
                ? "border-cyan-400/80 shadow-[0_0_40px_rgba(34,211,238,0.5)]"
                : "border-cyan-400/50 shadow-[0_0_30px_rgba(34,211,238,0.3)]",
              "bg-gradient-to-br from-slate-900/95 to-slate-800/95"
            )}
          >
            {/* Animated border glow - matching chat area */}
            <div className="pointer-events-none absolute inset-0 rounded-3xl rounded-l-none bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

            {/* Workspace Header (48px, matching status bar height) */}
            <div className="relative z-10 flex items-center justify-between border-b border-cyan-400/20 bg-slate-900/50 px-4 py-2.5">
              {/* Left: Title with icon */}
              <div className="flex items-center gap-2">
                <Code2 className="h-4 w-4 text-cyan-400" />
                <span className="text-sm font-medium text-cyan-400">Workspace</span>
              </div>

              {/* Middle: Code-Server URL copy button */}
              <button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(codeServerUrl)
                  } catch (err) {
                    console.error("Failed to copy:", err)
                  }
                }}
                className={cn(
                  "flex items-center gap-1.5 rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-400 transition-all duration-200",
                  // UX Best Practice: hover feedback
                  "hover:border-cyan-400/30 hover:bg-cyan-400/10 hover:text-cyan-400",
                  // UX Best Practice: focus state
                  "focus:outline-none focus:ring-2 focus:ring-cyan-400/50",
                  // UX Best Practice: cursor
                  "cursor-pointer"
                )}
                aria-label="Copy code-server URL"
              >
                <Copy className="h-3 w-3" />
                <span>Copy URL</span>
              </button>

              {/* Right: Close button */}
              <button
                onClick={() => setWorkspaceExpanded(false)}
                className={cn(
                  "rounded-lg border border-white/10 bg-white/5 p-1.5 text-slate-400 transition-all duration-200",
                  // UX Best Practice: hover feedback
                  "hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:text-cyan-400 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)]",
                  // UX Best Practice: focus state
                  "focus:outline-none focus:ring-2 focus:ring-cyan-400/50",
                  // UX Best Practice: cursor
                  "cursor-pointer"
                )}
                aria-label="Close workspace"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* iframe Container */}
            <div className="relative z-10 flex-1 overflow-hidden">
              {codeServerUrl ? (
                <iframe
                  src={codeServerUrl}
                  className="h-full w-full border-0 bg-slate-950"
                  title="Code-Server Workspace"
                  allow="clipboard-read; clipboard-write"
                  // UX Best Practice: Loading state handled by browser
                />
              ) : (
                // Loading state: UX Best Practice - show feedback during async operations
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-cyan-400" />
                    <p className="text-sm text-slate-400">Loading workspace...</p>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
