"use client"

/**
 * Real-time Chat Page - Session-based chat interface
 *
 * Features:
 * - Three-column layout: Sidebar + Chat Area + Session List
 * - Node-based session organization (Claude Code nodes only)
 * - Real-time WebSocket chat
 * - Message history loading
 * - Session creation, close, and archive
 */

import { useState, useEffect, useRef, useCallback, Fragment, memo } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Send,
  Loader2,
  StopCircle,
  Plus,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  ChevronUp,
  Bot,
  Archive,
  Lock,
  AlertCircle,
  Folder,
  FolderOpen,
  File,
  FileText,
  FileCode,
  RefreshCw,
  MoreVertical,
  List,
  LayoutList,
  FolderTree,
  Circle,
  Menu,
  Mic,
  Network,
  Terminal as TerminalIcon,
  X,
  Trash2,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { useWebSocket } from "@/contexts/websocket-context"
import { useVoiceInput } from "@/hooks/use-voice-input"
import {
  SessionMode,
  SessionStatus,
  LLMModel,
  NodeType,
  NodeStatus,
  MessageRole,
  MessageType,
  type NodeOut,
  type SessionOut,
  type MessageOut,
  type WorkspaceFileItem,
} from "@/lib/types"
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { SerializeAddon } from '@xterm/addon-serialize'
import '@xterm/xterm/css/xterm.css'

interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface NodeWithSessions extends NodeOut {
  sessions: SessionOut[]
  expanded: boolean
}

// Session tree node (for tree view)
interface SessionTreeNode extends SessionOut {
  children: SessionTreeNode[]
  depth: number
}

// Workspace file tree types (extend WorkspaceFileItem with expanded state)
interface FileNode extends WorkspaceFileItem {
  expanded?: boolean
}

type ViewMode = 'chat' | 'workspace'
type SessionListMode = 'detailed' | 'compact'
type SessionViewMode = 'tree' | 'grouped'

// ChatInput component - optimized to prevent parent re-renders on input
interface ChatInputProps {
  sessionId: string | null
  initialValue: string
  isLoading: boolean
  isConnected: boolean
  canSendMessage: boolean
  placeholder: string
  onSendMessage: (sessionId: string, message: string) => void
  onInterrupt: (sessionId: string) => void
  onInputChange: (sessionId: string, value: string) => void
}

const ChatInput = memo(function ChatInput({
  sessionId,
  initialValue,
  isLoading,
  isConnected,
  canSendMessage,
  placeholder,
  onSendMessage,
  onInterrupt,
  onInputChange,
}: ChatInputProps) {
  const [input, setInput] = useState(initialValue)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const savedInputRef = useRef("")

  // Voice input hook
  const { isRecording, isSupported, interimText, finalText, start, stop } = useVoiceInput(
    (final, interim) => {
      // Update input with saved text + final + interim
      const newInput = savedInputRef.current + final
      setInput(newInput)
      if (sessionId) {
        onInputChange(sessionId, newInput)
      }
    },
    {
      lang: "zh-CN",
      onError: (error) => {
        console.error("Voice recognition error:", error)
      }
    }
  )

  // Sync with external changes (e.g., session switch or clear after send)
  useEffect(() => {
    setInput(initialValue)
  }, [initialValue])

  // Auto-resize textarea based on content (optimized with direct DOM manipulation)
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = "auto"

    // Calculate new height (min 1 line, max 12 lines)
    const lineHeight = 24 // approximate line height
    const minHeight = lineHeight * 1 // 1 line for input
    const maxHeight = lineHeight * 12 // max 12 lines before scroll

    const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${newHeight}px`
  }, [input])

  // Auto-focus textarea when loading finishes
  useEffect(() => {
    if (!isLoading && sessionId && isConnected && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isLoading, sessionId, isConnected])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    setInput(value)
    if (sessionId) {
      onInputChange(sessionId, value)
    }
  }, [sessionId, onInputChange])

  const handleSend = useCallback(() => {
    if (!input.trim() || !sessionId || !isConnected || !canSendMessage || isLoading) return

    // Stop voice recording if it's active
    if (isRecording) {
      stop()
    }

    onSendMessage(sessionId, input)
    setInput("")

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [input, sessionId, isConnected, canSendMessage, isLoading, isRecording, stop, onSendMessage])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleInterruptClick = useCallback(() => {
    if (sessionId) {
      onInterrupt(sessionId)
    }
  }, [sessionId, onInterrupt])

  // Handle voice input button click
  const handleVoiceClick = useCallback(async () => {
    if (isRecording) {
      stop()
    } else {
      // Save current input before starting recording
      savedInputRef.current = input
      await start()
    }
  }, [isRecording, input, start, stop])

  return (
    <div className="border-t bg-background">
      <div className="bg-background overflow-hidden">
        <Textarea
          ref={textareaRef}
          value={isRecording ? savedInputRef.current + finalText + interimText : input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={isRecording ? "🎤 Listening..." : placeholder}
          disabled={isLoading || !isConnected || !canSendMessage || isRecording}
          className={`w-full resize-none overflow-y-auto border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 sm:px-3 pt-2 sm:pt-3 text-base ${isRecording ? "opacity-70" : ""}`}
          style={{ minHeight: "24px" }}
        />
        <div className="flex justify-end px-2 pb-2 gap-2">
          {/* Voice input button - only show if supported */}
          {isSupported && !isLoading && (
            <Button
              onClick={handleVoiceClick}
              variant={isRecording ? "destructive" : "outline"}
              size="icon"
              disabled={!isConnected || !canSendMessage}
              className={isRecording ? "animate-pulse" : ""}
            >
              {isRecording ? (
                <Circle className="h-4 w-4 fill-current" />
              ) : (
                <Mic className="h-4 w-4" />
              )}
            </Button>
          )}

          {/* Send/Interrupt button */}
          {isLoading ? (
            <Button onClick={handleInterruptClick} variant="destructive" size="icon">
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={handleSend}
              disabled={!input.trim() || !isConnected || !canSendMessage}
              size="icon"
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
})

// MessageItem component - optimized with memo to prevent re-renders
interface MessageItemProps {
  message: ParsedMessage
  isCollapsed: boolean
  onToggleCollapse: (messageId: string) => void
}

const MessageItem = memo(function MessageItem({
  message: msg,
  isCollapsed,
  onToggleCollapse,
}: MessageItemProps) {
  // Don't render assistant_result messages (stats shown in header)
  if (msg.message_type === MessageType.ASSISTANT_RESULT) {
    return null
  }

  const isUser = msg.role === MessageRole.USER
  const isThinking = msg.message_type === MessageType.ASSISTANT_THINKING
  const isSystemMessage = msg.message_type === MessageType.SYSTEM_MESSAGE
  const isToolUse = msg.message_type === MessageType.ASSISTANT_TOOL_USE
  const isToolOutput = msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT
  const isCollapsible = isThinking || isSystemMessage || isToolUse || isToolOutput

  const handleToggle = useCallback(() => {
    onToggleCollapse(msg.message_id)
  }, [msg.message_id, onToggleCollapse])

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 sm:mb-4`}
    >
      <div
        className={`max-w-[85%] sm:max-w-[80%] md:max-w-[70%] rounded-lg ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        } ${isCollapsible ? "px-2 py-1" : "px-3 sm:px-4 py-2"}`}
      >
        {isThinking ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">💭 思考中...</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0">
                {msg.contentParsed.message}
              </div>
            )}
          </div>
        ) : isSystemMessage ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">🔔 系统消息</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0">
                {msg.contentParsed.message}
              </div>
            )}
          </div>
        ) : isToolUse ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">🔧 {msg.contentParsed.tool_name}</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0 font-mono">
                {JSON.stringify(msg.contentParsed.tool_input, null, 2)}
              </div>
            )}
          </div>
        ) : isToolOutput ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">
                📤 {msg.contentParsed?.tool_name || 'Tool'} 结果
                {(msg.contentParsed?.tool_output === null || msg.contentParsed?.tool_output === undefined) && (
                  <span className="ml-1 text-xs opacity-50">(空)</span>
                )}
              </span>
            </div>
            {!isCollapsed && (
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0 font-mono">
                {(() => {
                  const output = msg.contentParsed?.tool_output
                  if (output === undefined || output === null) {
                    return <span className="text-muted-foreground italic">工具执行完成，无返回输出</span>
                  }
                  if (typeof output === 'string') {
                    return output.trim() || <span className="text-muted-foreground italic">空字符串</span>
                  }
                  return JSON.stringify(output, null, 2)
                })()}
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm whitespace-pre-wrap break-words">
            {msg.contentParsed.message}
          </div>
        )}
      </div>
    </div>
  )
})

export default function ChatPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = parseInt(params.mosaicId as string)
  const { isConnected, sendMessage, interrupt, sendRaw, subscribe } = useWebSocket()

  // Mobile detection
  const [isMobile, setIsMobile] = useState(false)
  const [sessionSheetOpen, setSessionSheetOpen] = useState(false)

  // View mode
  const [viewMode, setViewMode] = useState<ViewMode>('chat')

  // Session list mode
  const [sessionListMode, setSessionListMode] = useState<SessionListMode>('compact')
  const [sessionViewMode, setSessionViewMode] = useState<SessionViewMode>('grouped')
  const [treeExpandedSessions, setTreeExpandedSessions] = useState<Set<string>>(new Set())
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null)

  // Node and session management
  const [nodes, setNodes] = useState<NodeWithSessions[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-active-session`)
      return saved || null
    } catch (error) {
      return null
    }
  })
  const [messages, setMessages] = useState<ParsedMessage[]>([])

  // Workspace state
  const [fileTree, setFileTree] = useState<FileNode[]>([])
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string; language: string | null } | null>(null)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [fileContentLoading, setFileContentLoading] = useState(false)

  // Per-node workspace state tracking (to preserve selectedFile when switching sessions/nodes)
  const [nodeWorkspaceStates, setNodeWorkspaceStates] = useState<Record<string, {
    selectedFile: { path: string; content: string; language: string | null } | null
  }>>({})

  // Terminal panel state (for workspace mode)
  const [terminalHeight, setTerminalHeight] = useState<number>(() => {
    if (typeof window === 'undefined') return 300
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-terminal-height`)
      return saved ? parseInt(saved, 10) : 300
    } catch (error) {
      return 300
    }
  })
  const [terminalCollapsed, setTerminalCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-terminal-collapsed`)
      return saved === 'true'
    } catch (error) {
      return false
    }
  })
  const [isTerminalResizing, setIsTerminalResizing] = useState(false)
  const terminalResizeStartY = useRef<number>(0)
  const terminalResizeStartHeight = useRef<number>(0)

  // XTerm terminal instances map (session_id -> {terminal, fitAddon, serializeAddon, serializedContent})
  const terminalsMapRef = useRef<Map<string, {
    terminal: Terminal | null,
    fitAddon: FitAddon | null,
    serializeAddon: SerializeAddon | null,
    serializedContent: string  // Store serialized terminal content for recreation
  }>>(new Map())
  const terminalRef = useRef<HTMLDivElement>(null)
  const currentAttachedTerminalRef = useRef<string | null>(null) // Track which terminal is currently attached to DOM

  // Workspace sidebar state (resizable & collapsible)
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    if (typeof window === 'undefined') return 280
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-sidebar-width`)
      return saved ? parseInt(saved, 10) : 280
    } catch (error) {
      return 280
    }
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-sidebar-collapsed`)
      return saved === 'true'
    } catch (error) {
      return false
    }
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeStartX = useRef<number>(0)
  const resizeStartWidth = useRef<number>(0)

  // Input and loading states
  // Store input per session to preserve content when switching sessions
  // Initialize from localStorage to persist across page navigation
  const [sessionInputs, setSessionInputs] = useState<Record<string, string>>(() => {
    if (typeof window === 'undefined') return {}
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-session-inputs`)
      return saved ? JSON.parse(saved) : {}
    } catch (error) {
      console.error("Failed to load session inputs from localStorage:", error)
      return {}
    }
  })
  // Store loading state per session to allow independent message sending
  const [sessionLoadings, setSessionLoadings] = useState<Record<string, boolean>>({})

  // Get current session's input and loading state
  const currentInput = activeSessionId ? (sessionInputs[activeSessionId] || "") : ""
  const currentLoading = activeSessionId ? (sessionLoadings[activeSessionId] || false) : false

  // Session usage statistics
  const [sessionStats, setSessionStats] = useState<{
    total_cost_usd?: number
    total_input_tokens?: number
    total_output_tokens?: number
  } | null>(null)

  // Collapsed messages (thinking, system, and tool use messages, by message_id)
  const [collapsedMessages, setCollapsedMessages] = useState<Set<string>>(new Set())

  // Session scroll state tracking
  const [sessionScrollStates, setSessionScrollStates] = useState<Record<string, {
    scrollTop: number
    messageCount: number
    wasAtBottom: boolean
  }>>({})

  // Track scroll restoration and message updates
  const justSwitchedSessionRef = useRef<boolean>(false)
  const prevMessageCountRef = useRef<number>(0)
  const hasInitiallyScrolledRef = useRef<Record<string, boolean>>({}) // Track if we've done initial scroll for each session-view combo

  // Create session dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [sessionMode, setSessionMode] = useState<SessionMode>(SessionMode.CHAT)
  const [sessionModel, setSessionModel] = useState<LLMModel>(LLMModel.SONNET)
  const [creating, setCreating] = useState(false)

  // Close session confirmation dialog state
  const [closeDialogOpen, setCloseDialogOpen] = useState(false)
  const [closingSession, setClosingSession] = useState<{ sessionId: string; nodeId: string } | null>(null)
  const [closing, setClosing] = useState(false)

  // Batch archive confirmation dialog state
  const [batchArchiveDialogOpen, setBatchArchiveDialogOpen] = useState(false)
  const [batchArchivingNode, setBatchArchivingNode] = useState<{ nodeId: string; closedSessionIds: string[] } | null>(null)
  const [batchArchiving, setBatchArchiving] = useState(false)

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const maxSequenceRef = useRef<number>(0) // Track max sequence number for gap detection
  const sessionStartedResolvers = useRef<Map<string, (value: boolean) => void>>(new Map())
  const sessionMessageCounts = useRef<Record<string, number>>({}) // Track message count per session-view combo
  const prevActiveSessionId = useRef<string | null>(null)
  const prevViewMode = useRef<ViewMode>('chat')
  const prevNodeId = useRef<string | null>(null) // Track previous node ID for workspace state

  // Utility function to check if user is at bottom of messages
  const isAtBottom = useCallback(() => {
    const container = messagesContainerRef.current
    if (!container) return true
    const threshold = 100 // Within 100px of bottom counts as "at bottom"
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold
  }, [])

  // Wrapper function to set active session and persist to localStorage
  const selectSession = useCallback((sessionId: string | null) => {
    setActiveSessionId(sessionId)
    if (typeof window !== 'undefined') {
      try {
        if (sessionId) {
          localStorage.setItem(`mosaic-${mosaicId}-active-session`, sessionId)
        } else {
          localStorage.removeItem(`mosaic-${mosaicId}-active-session`)
        }
      } catch (error) {
        console.error("Failed to save active session to localStorage:", error)
      }
    }
  }, [mosaicId])

  // Load nodes and sessions function
  // autoSelectSession: whether to automatically select a session when no session is active
  const loadNodesAndSessions = useCallback(async (autoSelectSession = true) => {
    try {
      // Load all nodes
      const nodesData = await apiClient.listNodes(mosaicId)
      // Filter only Claude Code nodes and sort by node_id
      const ccNodes = nodesData
        .filter((n) => n.node_type === NodeType.CLAUDE_CODE)
        .sort((a, b) => a.node_id.localeCompare(b.node_id))

      if (ccNodes.length === 0) {
        setNodes([])
        return
      }

      // Load all active and closed sessions for this mosaic (exclude archived)
      // Use a large page_size to get all sessions in one request
      const allSessionsData = await apiClient.listSessions(mosaicId, undefined, {
        page: 1,
        page_size: 1000, // Large number to get all sessions
      })

      // Filter only active and closed sessions (exclude archived)
      const activeSessions = allSessionsData.items.filter(
        (s) => s.status === SessionStatus.ACTIVE || s.status === SessionStatus.CLOSED
      )

      // Group sessions by node_id
      const sessionsByNode = new Map<string, SessionOut[]>()
      activeSessions.forEach((session) => {
        if (!sessionsByNode.has(session.node_id)) {
          sessionsByNode.set(session.node_id, [])
        }
        sessionsByNode.get(session.node_id)!.push(session)
      })

      // Sort sessions within each node by created_at (newest first)
      sessionsByNode.forEach((sessions) => {
        sessions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      })

      // Build nodes with sessions
      const nodesWithSessions: NodeWithSessions[] = ccNodes.map((node) => ({
        ...node,
        sessions: sessionsByNode.get(node.node_id) || [],
        expanded: true, // Default expanded
      }))

      setNodes(nodesWithSessions)

      // Only auto-select session if the flag is true
      if (autoSelectSession) {
        // Auto-select session (prioritize saved session, then first active session)
        const allSessions = nodesWithSessions.flatMap((n) => n.sessions)

        // 1. Check if there's a saved session selection
        const savedSessionId = typeof window !== 'undefined'
          ? localStorage.getItem(`mosaic-${mosaicId}-active-session`)
          : null

        let shouldSetSession = false
        let targetSessionId = null

        // 2. If saved session exists and is still available (not archived), restore it
        if (savedSessionId && allSessions.some(s => s.session_id === savedSessionId)) {
          targetSessionId = savedSessionId
          shouldSetSession = true
        } else if (!activeSessionId) {
          // 3. Only select a new session if no session is currently active
          // This prevents auto-selection after archiving
          const activeSession = allSessions.find((s) => s.status === SessionStatus.ACTIVE)
          if (activeSession) {
            targetSessionId = activeSession.session_id
            shouldSetSession = true
          } else if (allSessions.length > 0) {
            // If no active session, select first one (to view history)
            targetSessionId = allSessions[0].session_id
            shouldSetSession = true
          }
        }

        // 4. Only update if needed (avoid unnecessary re-renders)
        if (shouldSetSession && targetSessionId !== activeSessionId) {
          selectSession(targetSessionId)
        }
      }
    } catch (error) {
      console.error("Failed to load nodes and sessions:", error)
    }
  }, [mosaicId, selectSession])

  // Mobile detection effect
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Load nodes and sessions on mount
  useEffect(() => {
    if (!token) return
    loadNodesAndSessions()
  }, [token, loadNodesAndSessions])

  // Listen for mosaic status changes and refresh node/session list
  useEffect(() => {
    const handleMosaicStatusChange = (event: Event) => {
      const customEvent = event as CustomEvent<{ status: string; mosaicId: number }>
      // Only refresh if it's the current mosaic
      if (customEvent.detail.mosaicId === mosaicId) {
        console.log("[Chat] Mosaic status changed, refreshing nodes and sessions...")
        loadNodesAndSessions()
      }
    }

    window.addEventListener('mosaic-status-changed', handleMosaicStatusChange)

    return () => {
      window.removeEventListener('mosaic-status-changed', handleMosaicStatusChange)
    }
  }, [mosaicId, loadNodesAndSessions])

  // Subscribe to global WebSocket notifications (session lifecycle events)
  useEffect(() => {
    const unsubscribe = subscribe('*', (message) => {
      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        return
      }

      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Handle notification messages (session lifecycle events)
      if (wsMessage.role === "notification") {
        console.log("[Chat] Received global notification:", wsMessage.message_type)
        if (wsMessage.message_type === "session_started") {
          console.log("[Chat] Session started, refreshing session list")

          // Refresh session list first, then resolve waiter
          loadNodesAndSessions().then(() => {
            // Resolve any pending session creation waiter
            if (wsMessage.payload?.session_id) {
              const resolver = sessionStartedResolvers.current.get(wsMessage.payload.session_id)
              if (resolver) {
                console.log("[Chat] Resolving session_started promise for", wsMessage.payload.session_id)
                resolver(true)
                sessionStartedResolvers.current.delete(wsMessage.payload.session_id)
              }
            }
          })
        }
        if (wsMessage.message_type === "session_ended") {
          console.log("[Chat] Session ended, refreshing session list")
          loadNodesAndSessions()
        }
      }
    })

    return () => {
      unsubscribe()
    }
  }, [subscribe, loadNodesAndSessions])

  // Save scroll position when switching away from a session or view mode
  useEffect(() => {
    const prevSessionId = prevActiveSessionId.current
    const prevMode = prevViewMode.current
    const currentSessionId = activeSessionId
    const currentMode = viewMode

    // Save scroll state if session or view mode changed
    if (prevSessionId && (prevSessionId !== currentSessionId || prevMode !== currentMode)) {
      const container = messagesContainerRef.current
      if (container) {
        const stateKey = `${prevSessionId}-${prevMode}`
        const messageCount = sessionMessageCounts.current[stateKey] || 0
        const scrollTop = container.scrollTop
        const wasAtBottom = isAtBottom()

        console.log(`[Scroll Save] Saving scroll state for ${stateKey}:`, {
          scrollTop,
          messageCount,
          wasAtBottom
        })

        setSessionScrollStates(prev => ({
          ...prev,
          [stateKey]: {
            scrollTop,
            messageCount,
            wasAtBottom
          }
        }))

        // Clear the initialized flag for the session we're leaving
        // This ensures proper re-initialization when we come back
        delete hasInitiallyScrolledRef.current[stateKey]
      }
    }

    // Mark that we just switched sessions
    if (currentSessionId && (prevSessionId !== currentSessionId || prevMode !== currentMode)) {
      justSwitchedSessionRef.current = true
      prevMessageCountRef.current = 0 // Reset message count for new session
      console.log(`[Session Switch] Switched to ${currentSessionId}-${currentMode}`)
    }

    // Update refs for next comparison
    prevActiveSessionId.current = currentSessionId
    prevViewMode.current = currentMode
  }, [activeSessionId, viewMode, isAtBottom])

  // Handle nodes loading completion - load messages when nodes first become available
  // This handles the case where activeSessionId is restored from localStorage before nodes load
  const prevNodesLength = useRef(0)
  useEffect(() => {
    // Detect when nodes change from empty to non-empty (first load only)
    const nodesJustLoaded = prevNodesLength.current === 0 && nodes.length > 0
    prevNodesLength.current = nodes.length

    // If nodes just loaded and we have an active session without messages, load them
    if (nodesJustLoaded && activeSessionId) {
      setSessionLoadings(prev => ({
        ...prev,
        [activeSessionId]: true
      }))
      loadMessages(activeSessionId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, activeSessionId])

  // Subscribe to WebSocket messages for active session
  useEffect(() => {
    if (!activeSessionId) return

    // Wait until nodes are loaded before loading messages
    if (nodes.length === 0) return

    // Immediately clear messages and show loading state when switching sessions
    setMessages([])
    setSessionLoadings(prev => ({
      ...prev,
      [activeSessionId]: true
    }))

    // Load message history from database
    loadMessages(activeSessionId)

    // Reset session stats and collapsed messages when switching sessions
    setSessionStats(null)
    setCollapsedMessages(new Set())

    // Reset sequence tracking
    maxSequenceRef.current = 0

    // Subscribe to messages for this session
    const unsubscribe = subscribe(activeSessionId, (message) => {
      console.log("[Chat] Received message:", message)

      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        console.error("[Chat] WebSocket error:", message.message)
        return
      }

      // Type assertion: we've checked it's not an error, so it must be WSMessage
      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Verify session_id matches (double-check even though context already filters)
      if (wsMessage.session_id !== activeSessionId) {
        console.warn("[Chat] Ignoring message from different session:", wsMessage.session_id)
        return
      }

      // Check for sequence gap (message loss detection)
      if (maxSequenceRef.current > 0) {
        const expectedSequence = maxSequenceRef.current + 1
        if (wsMessage.sequence > expectedSequence) {
          console.warn(
            `[Chat] Sequence gap detected! Expected ${expectedSequence}, got ${wsMessage.sequence}. Reloading messages...`
          )
          // Reload all messages from database to fill the gap
          loadMessages(activeSessionId)
          return
        }
      }

      // Update max sequence number
      maxSequenceRef.current = Math.max(maxSequenceRef.current, wsMessage.sequence)

      // Handle terminal messages - ALWAYS intercept, regardless of terminal instance
      // These messages should NEVER appear in chat area
      // Route messages to the correct terminal instance based on session_id
      if (wsMessage.message_type === 'terminal_output') {
        console.log('[Terminal] Received terminal_output:', {
          session_id: wsMessage.session_id,
          data_length: wsMessage.payload?.data?.length
        })

        // Route to the terminal instance for this session
        const sessionId = wsMessage.session_id
        if (sessionId && wsMessage.payload?.data) {
          const terminalData = terminalsMapRef.current.get(sessionId)
          if (terminalData && terminalData.terminal) {
            // Write directly to terminal (serialization will capture everything)
            terminalData.terminal.write(wsMessage.payload.data)
          }
        }
        return // Always intercept - don't add to message list
      }

      if (wsMessage.message_type === 'terminal_status') {
        console.log('[Terminal] Received terminal_status:', {
          session_id: wsMessage.session_id,
          status: wsMessage.payload?.status
        })

        // Route to the terminal instance for this session
        const sessionId = wsMessage.session_id
        if (sessionId) {
          const terminalData = terminalsMapRef.current.get(sessionId)
          if (terminalData) {
            if (wsMessage.payload?.status === 'started') {
              const msg = '\r\nTerminal connected.\r\n'
              if (terminalData.terminal) {
                terminalData.terminal.write(msg)
              }
            } else if (wsMessage.payload?.status === 'stopped') {
              const msg = '\r\nTerminal disconnected.\r\n'
              if (terminalData.terminal) {
                terminalData.terminal.write(msg)
              }
            } else if (wsMessage.payload?.status === 'error' && wsMessage.payload?.message) {
              const msg = `\r\n\x1b[31mError: ${wsMessage.payload.message}\x1b[0m\r\n`
              if (terminalData.terminal) {
                terminalData.terminal.write(msg)
              }
            }
          }
        }
        return // Always intercept - don't add to message list
      }

      // Skip notification messages (they are for logic only, not for display)
      if (wsMessage.role === 'notification') {
        console.log("[Chat] Skipping notification message (not for display):", wsMessage)
        return
      }

      // Update session statistics if this is a result message
      if (wsMessage.message_type === "assistant_result" && wsMessage.payload) {
        setSessionStats({
          total_cost_usd: wsMessage.payload.total_cost_usd,
          total_input_tokens: wsMessage.payload.total_input_tokens,
          total_output_tokens: wsMessage.payload.total_output_tokens,
        })
      }

      // All non-notification messages should have message_id
      if (!wsMessage.message_id) {
        console.error("[Chat] Non-notification message missing message_id:", wsMessage)
        return
      }

      // Add message to list
      const newMessage: ParsedMessage = {
        id: 0, // Will be replaced by server
        message_id: wsMessage.message_id,
        user_id: 0, // Will be filled by server
        mosaic_id: mosaicId,
        node_id: "", // Will be filled by server
        session_id: activeSessionId,
        role: wsMessage.role as MessageRole,
        message_type: wsMessage.message_type as MessageType,
        payload: wsMessage.payload,
        contentParsed: wsMessage.payload,
        sequence: wsMessage.sequence,
        created_at: wsMessage.timestamp,
      }

      setMessages((prev) => [...prev, newMessage])

      // Collapse thinking, system, and tool use messages by default
      if (wsMessage.message_type === "assistant_thinking" || wsMessage.message_type === "system_message" || wsMessage.message_type === "assistant_tool_use" || wsMessage.message_type === "assistant_tool_output") {
        setCollapsedMessages((prev) => new Set(prev).add(wsMessage.message_id!)) // message_id is guaranteed to exist (checked above)
      }

      // Stop loading on result
      if (wsMessage.message_type === "assistant_result") {
        setSessionLoadings(prev => ({
          ...prev,
          [activeSessionId]: false
        }))
      }
    })

    // Cleanup subscription on unmount or session change
    return () => {
      unsubscribe()
    }
  }, [activeSessionId, subscribe])

  // Save session inputs to localStorage whenever they change
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(
        `mosaic-${mosaicId}-session-inputs`,
        JSON.stringify(sessionInputs)
      )
    } catch (error) {
      console.error("Failed to save session inputs to localStorage:", error)
    }
  }, [sessionInputs, mosaicId])

  // Track message count for current session-view combo
  useEffect(() => {
    if (!activeSessionId) return
    const stateKey = `${activeSessionId}-${viewMode}`
    sessionMessageCounts.current[stateKey] = messages.length
  }, [messages.length, activeSessionId, viewMode])

  // Handle scroll restoration when switching sessions or initial load
  useEffect(() => {
    if (!activeSessionId) return

    const container = messagesContainerRef.current
    if (!container) return

    const stateKey = `${activeSessionId}-${viewMode}`

    // Check if we need to handle initial scroll for this session
    const needsInitialScroll = !hasInitiallyScrolledRef.current[stateKey] && messages.length > 0

    // Skip if we haven't switched sessions and already initialized
    if (!justSwitchedSessionRef.current && !needsInitialScroll) return

    // Wait for messages to load
    if (messages.length === 0) return

    const savedState = sessionScrollStates[stateKey]

    // We have messages loaded, time to restore or initialize scroll
    justSwitchedSessionRef.current = false // Reset the flag
    hasInitiallyScrolledRef.current[stateKey] = true // Mark this session as initialized

    console.log(`[Scroll Restore] Processing scroll for ${stateKey}, message count: ${messages.length}, has saved state: ${!!savedState}`)

    if (savedState) {
      console.log(`[Scroll Restore] Restoring scroll for ${stateKey}:`, savedState)

      // Check if new messages arrived while we were away
      if (messages.length > savedState.messageCount && savedState.wasAtBottom) {
        // User was at bottom before, scroll to bottom to see new messages
        console.log(`[Scroll Restore] User was at bottom, showing new messages`)
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (container) {
              container.scrollTop = container.scrollHeight
            }
            setTimeout(() => {
              if (container) {
                container.scrollTop = container.scrollHeight
              }
            }, 50)
          })
        })
      } else {
        // Restore exact scroll position
        console.log(`[Scroll Restore] Restoring to saved position: ${savedState.scrollTop}`)
        requestAnimationFrame(() => {
          if (container) {
            container.scrollTop = savedState.scrollTop
          }
          // Double-check after a delay
          setTimeout(() => {
            if (container && Math.abs(container.scrollTop - savedState.scrollTop) > 10) {
              console.log(`[Scroll Restore] Re-applying scroll position`)
              container.scrollTop = savedState.scrollTop
            }
          }, 100)
        })
      }
    } else {
      // First time in this session, scroll to bottom
      console.log(`[Scroll Restore] First time in session, scrolling to bottom`)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (container) {
            container.scrollTop = container.scrollHeight
          }
          setTimeout(() => {
            if (container) {
              container.scrollTop = container.scrollHeight
            }
          }, 50)
        })
      })
    }

    // Update the message count tracker
    prevMessageCountRef.current = messages.length
  }, [messages.length, activeSessionId, viewMode, sessionScrollStates])

  // Handle auto-scroll for new messages in the current session
  useEffect(() => {
    if (!activeSessionId) return

    const container = messagesContainerRef.current
    if (!container) return

    const stateKey = `${activeSessionId}-${viewMode}`

    // Skip if we haven't done initial scroll yet (still loading)
    if (!hasInitiallyScrolledRef.current[stateKey]) return

    // Skip if we just switched sessions (handled by the other effect)
    if (justSwitchedSessionRef.current) return

    // Check if we have new messages (and not just cleared messages)
    const hasNewMessages = messages.length > prevMessageCountRef.current && prevMessageCountRef.current > 0

    if (hasNewMessages) {
      // Check if user is currently at bottom
      const currentlyAtBottom = isAtBottom()

      console.log(`[New Message] New message detected in current session. At bottom: ${currentlyAtBottom}`)

      if (currentlyAtBottom) {
        // User is at bottom, auto-scroll to show new message
        console.log(`[New Message] Auto-scrolling to bottom`)
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (container) {
              container.scrollTop = container.scrollHeight
            }
            setTimeout(() => {
              if (container) {
                container.scrollTop = container.scrollHeight
              }
            }, 50)
          })
        })
      } else {
        console.log(`[New Message] User is scrolled up, not auto-scrolling`)
      }
    }

    // Update the message count tracker
    prevMessageCountRef.current = messages.length
  }, [messages, activeSessionId, viewMode, isAtBottom])

  // Cleanup pending session_started resolvers on unmount
  useEffect(() => {
    return () => {
      sessionStartedResolvers.current.clear()
    }
  }, [])

  // Load workspace files
  const loadWorkspace = async (nodeId: string) => {
    if (!nodeId) return

    try {
      setWorkspaceLoading(true)
      const data = await apiClient.listWorkspaceFiles(mosaicId, nodeId, {
        path: '/',
        recursive: false,
        max_depth: 1
      })

      // Convert WorkspaceFileItem[] to FileNode[] (add expanded property)
      const convertToFileNodes = (items: WorkspaceFileItem[]): FileNode[] => {
        return items.map(item => ({
          ...item,
          expanded: false,
          // 目录：children 为 undefined（未加载）或已加载的数组
          // 文件：children 为 undefined（不需要 children）
          children: item.type === 'directory'
            ? (item.children ? convertToFileNodes(item.children) : undefined)
            : undefined
        }))
      }

      setFileTree(convertToFileNodes(data.items))
    } catch (error) {
      console.error("Failed to load workspace:", error)
      setFileTree([])
    } finally {
      setWorkspaceLoading(false)
    }
  }

  // Sidebar resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    resizeStartX.current = e.clientX
    resizeStartWidth.current = sidebarWidth
  }, [sidebarWidth])

  const handleResizeMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return

    const deltaX = e.clientX - resizeStartX.current
    const newWidth = resizeStartWidth.current + deltaX

    // Constrain width between min (200px) and max (600px)
    const constrainedWidth = Math.min(Math.max(newWidth, 200), 600)
    setSidebarWidth(constrainedWidth)
  }, [isResizing])

  const handleResizeEnd = useCallback(() => {
    if (!isResizing) return
    setIsResizing(false)
  }, [isResizing])

  // Sidebar collapse toggle
  const toggleSidebarCollapse = useCallback(() => {
    setSidebarCollapsed(prev => !prev)
  }, [])

  // Terminal panel resize handlers (vertical resize)
  const handleTerminalResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsTerminalResizing(true)
    terminalResizeStartY.current = e.clientY
    terminalResizeStartHeight.current = terminalHeight
  }, [terminalHeight])

  const handleTerminalResizeMove = useCallback((e: MouseEvent) => {
    if (!isTerminalResizing) return

    const deltaY = terminalResizeStartY.current - e.clientY // Reversed because we drag up to increase height
    const newHeight = terminalResizeStartHeight.current + deltaY

    // Constrain height between min (150px) and max (800px)
    const constrainedHeight = Math.min(Math.max(newHeight, 150), 800)
    setTerminalHeight(constrainedHeight)
  }, [isTerminalResizing])

  const handleTerminalResizeEnd = useCallback(() => {
    if (!isTerminalResizing) return
    setIsTerminalResizing(false)
  }, [isTerminalResizing])

  // Terminal collapse toggle
  const toggleTerminalCollapse = useCallback(() => {
    setTerminalCollapsed(prev => !prev)
  }, [])

  // Attach global mouse event listeners for resizing
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove)
      document.addEventListener('mouseup', handleResizeEnd)
      // Prevent text selection while resizing
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'

      return () => {
        document.removeEventListener('mousemove', handleResizeMove)
        document.removeEventListener('mouseup', handleResizeEnd)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
    }
  }, [isResizing, handleResizeMove, handleResizeEnd])

  // Save sidebar width to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-sidebar-width`, sidebarWidth.toString())
    } catch (error) {
      console.error("Failed to save sidebar width to localStorage:", error)
    }
  }, [sidebarWidth, mosaicId])

  // Save sidebar collapsed state to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-sidebar-collapsed`, sidebarCollapsed.toString())
    } catch (error) {
      console.error("Failed to save sidebar collapsed state to localStorage:", error)
    }
  }, [sidebarCollapsed, mosaicId])

  // Attach global mouse event listeners for terminal resizing
  useEffect(() => {
    if (isTerminalResizing) {
      document.addEventListener('mousemove', handleTerminalResizeMove)
      document.addEventListener('mouseup', handleTerminalResizeEnd)
      // Prevent text selection while resizing
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'row-resize'

      return () => {
        document.removeEventListener('mousemove', handleTerminalResizeMove)
        document.removeEventListener('mouseup', handleTerminalResizeEnd)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
    }
  }, [isTerminalResizing, handleTerminalResizeMove, handleTerminalResizeEnd])

  // Save terminal height to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-terminal-height`, terminalHeight.toString())
    } catch (error) {
      console.error("Failed to save terminal height to localStorage:", error)
    }
  }, [terminalHeight, mosaicId])

  // Save terminal collapsed state to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-terminal-collapsed`, terminalCollapsed.toString())
    } catch (error) {
      console.error("Failed to save terminal collapsed state to localStorage:", error)
    }
  }, [terminalCollapsed, mosaicId])

  // Initialize XTerm terminal when in workspace mode (multi-instance support)
  useEffect(() => {
    // Handle terminal creation and visibility
    if (viewMode === 'workspace' && !terminalCollapsed && terminalRef.current && activeSessionId) {

      // Get or create terminal data for this session
      let terminalData = terminalsMapRef.current.get(activeSessionId)

      if (!terminalData) {
        // First time - initialize terminal data structure
        terminalData = {
          terminal: null,
          fitAddon: null,
          serializeAddon: null,
          serializedContent: ''
        }
        terminalsMapRef.current.set(activeSessionId, terminalData)
      }

      console.log('[Terminal] Creating fresh terminal instance for session:', activeSessionId)

      const term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'monospace, "Courier New", Courier',
        theme: {
          background: '#1a1a1a',
          foreground: '#00ff00',
          cursor: '#00ff00',
          cursorAccent: '#1a1a1a',
        },
        convertEol: true,
        scrollback: 1000,
      })

      const fit = new FitAddon()
      const serialize = new SerializeAddon()
      term.loadAddon(fit)
      term.loadAddon(serialize)

      // Clear the container and open terminal
      terminalRef.current.innerHTML = ''
      term.open(terminalRef.current)
      fit.fit()

      // Restore serialized content if exists
      if (terminalData.serializedContent) {
        console.log('[Terminal] Restoring serialized content, length:', terminalData.serializedContent.length)
        term.write(terminalData.serializedContent)
      } else {
        // Display welcome message for new terminals
        term.writeln('Welcome to Mosaic Terminal')
        term.writeln('Waiting for connection...')
        term.writeln('')
      }

      // Handle user input - capture session ID in closure
      const sessionId = activeSessionId
      term.onData((data) => {
        console.log('[Terminal] Sending terminal_input, session:', sessionId, 'data length:', data.length)
        sendRaw({
          session_id: sessionId,
          type: 'terminal_input',
          data: data
        })
      })

      // Update terminal data
      terminalData.terminal = term
      terminalData.fitAddon = fit
      terminalData.serializeAddon = serialize

      // Update current attached terminal
      currentAttachedTerminalRef.current = activeSessionId

      // Send terminal_start message if this is the first terminal for this session
      if (!terminalData.serializedContent) {
        console.log('[Terminal] Sending terminal_start for session:', activeSessionId)
        sendRaw({
          session_id: activeSessionId,
          type: 'terminal_start'
        })

        // Send initial newline to trigger bash prompt display
        setTimeout(() => {
          sendRaw({
            session_id: activeSessionId,
            type: 'terminal_input',
            data: '\r'
          })
        }, 200)
      }

      term.focus()
    }

    // Cleanup function - save serialized content and dispose terminal when DOM unmounts
    return () => {
      if (activeSessionId && currentAttachedTerminalRef.current === activeSessionId) {
        const terminalData = terminalsMapRef.current.get(activeSessionId)
        if (terminalData && terminalData.terminal && terminalData.serializeAddon) {
          console.log('[Terminal] Saving serialized content and disposing terminal for session:', activeSessionId)

          // Save current terminal serialized content
          terminalData.serializedContent = terminalData.serializeAddon.serialize()

          // Dispose the terminal
          terminalData.terminal.dispose()
          terminalData.terminal = null
          terminalData.fitAddon = null
          terminalData.serializeAddon = null
        }
        currentAttachedTerminalRef.current = null
      }
    }
  }, [viewMode, terminalCollapsed, activeSessionId, sendRaw])

  // Handle terminal resize (multi-instance support)
  useEffect(() => {
    if (viewMode === 'workspace' && !terminalCollapsed && activeSessionId) {
      const terminalData = terminalsMapRef.current.get(activeSessionId)
      if (terminalData && terminalData.terminal && terminalData.fitAddon) {
        // Small delay to ensure DOM is updated
        const timeoutId = setTimeout(() => {
          if (terminalData.fitAddon && terminalData.terminal) {
            terminalData.fitAddon.fit()

            // Notify backend of new size
            sendRaw({
              session_id: activeSessionId,
              type: 'terminal_resize',
              cols: terminalData.terminal.cols,
              rows: terminalData.terminal.rows
            })
          }
        }, 100)

        return () => clearTimeout(timeoutId)
      }
    }
  }, [terminalHeight, terminalCollapsed, viewMode, activeSessionId, sendRaw])

  // Save workspace state when switching away from a node
  useEffect(() => {
    // Find current node ID from active session
    let currentNodeId: string | null = null
    if (activeSessionId) {
      for (const node of nodes) {
        const session = node.sessions.find((s) => s.session_id === activeSessionId)
        if (session) {
          currentNodeId = node.node_id
          break
        }
      }
    }

    const prevNode = prevNodeId.current

    // Save previous node's selectedFile state if node changed
    if (prevNode && prevNode !== currentNodeId) {
      // Save the current selectedFile before switching
      setNodeWorkspaceStates(prev => ({
        ...prev,
        [prevNode]: { selectedFile }
      }))
    }

    // Update ref for next comparison
    prevNodeId.current = currentNodeId
  }, [activeSessionId, nodes, selectedFile])

  // Load workspace and restore state when switching to workspace view or when active session changes
  useEffect(() => {
    if (viewMode !== 'workspace' || !activeSessionId) return

    // Find node ID from active session
    let nodeId: string | null = null
    for (const node of nodes) {
      const session = node.sessions.find((s) => s.session_id === activeSessionId)
      if (session) {
        nodeId = node.node_id
        break
      }
    }

    if (nodeId) {
      loadWorkspace(nodeId)

      // Restore this node's selectedFile state if available
      const savedState = nodeWorkspaceStates[nodeId]
      if (savedState?.selectedFile) {
        setSelectedFile(savedState.selectedFile)
      } else {
        // Clear selectedFile when switching to a node with no saved state
        setSelectedFile(null)
      }
    }
  }, [viewMode, activeSessionId, nodes])

  const loadMessages = async (sessionId: string) => {
    try {
      // Safety check: ensure nodes are loaded
      if (nodes.length === 0) {
        console.warn("loadMessages called but nodes not yet loaded, skipping...")
        return
      }

      // Find the session's node_id
      let nodeId: string | null = null
      for (const node of nodes) {
        const session = node.sessions.find((s) => s.session_id === sessionId)
        if (session) {
          nodeId = node.node_id
          break
        }
      }

      if (!nodeId) {
        console.error("Node not found for session:", sessionId)
        return
      }

      const data = await apiClient.listMessages(mosaicId, {
        nodeId,
        sessionId,
        page: 1,
        pageSize: 9999
      })
      const parsed = data.items.map((msg) => ({
        ...msg,
        contentParsed: typeof msg.payload === "string" ? JSON.parse(msg.payload) : msg.payload,
      }))

      // Debug: Log all tool_output messages from database
      const toolOutputMessages = parsed.filter(msg => msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT)
      if (toolOutputMessages.length > 0) {
        console.log("[Chat] Loaded tool_output messages from DB:", toolOutputMessages.map(msg => ({
          message_id: msg.message_id,
          message_type: msg.message_type,
          role: msg.role,
          sequence: msg.sequence,
          payload: msg.payload,
          contentParsed: msg.contentParsed
        })))
      }

      setMessages(parsed)

      // Update max sequence number from loaded messages
      if (parsed.length > 0) {
        const maxSeq = Math.max(...parsed.map((msg) => msg.sequence))
        maxSequenceRef.current = maxSeq
        console.log("[Chat] Loaded messages, max sequence:", maxSeq)
      } else {
        maxSequenceRef.current = 0
      }

      // Collapse all thinking, system, and tool use messages by default
      const collapsibleIds = parsed
        .filter((msg) => msg.message_type === MessageType.ASSISTANT_THINKING || msg.message_type === MessageType.SYSTEM_MESSAGE || msg.message_type === MessageType.ASSISTANT_TOOL_USE || msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT)
        .map((msg) => msg.message_id)
      setCollapsedMessages(new Set(collapsibleIds))

      // Extract session stats from the last assistant_result message
      const lastResult = [...parsed].reverse().find((msg) => msg.message_type === MessageType.ASSISTANT_RESULT)
      if (lastResult && lastResult.contentParsed) {
        setSessionStats({
          total_cost_usd: lastResult.contentParsed.total_cost_usd,
          total_input_tokens: lastResult.contentParsed.total_input_tokens,
          total_output_tokens: lastResult.contentParsed.total_output_tokens,
        })
      }

      // Restore loading state based on last message
      // If messages exist and the last message is not ASSISTANT_RESULT, session is still processing
      if (parsed.length > 0) {
        const lastMessage = parsed[parsed.length - 1]
        const isProcessing = lastMessage.message_type !== MessageType.ASSISTANT_RESULT
        setSessionLoadings(prev => ({
          ...prev,
          [sessionId]: isProcessing
        }))
        if (isProcessing) {
          console.log("[Chat] Session is still processing, restored loading state for", sessionId)
        }
      } else {
        // No messages, session is ready for input
        setSessionLoadings(prev => ({
          ...prev,
          [sessionId]: false
        }))
      }
    } catch (error) {
      console.error("Failed to load messages:", error)
    }
  }

  // Callback for ChatInput component - send message
  const handleSendMessage = useCallback((sessionId: string, message: string) => {
    try {
      // Send message via global WebSocket
      sendMessage(sessionId, message)
      // Clear current session's input
      setSessionInputs(prev => ({
        ...prev,
        [sessionId]: ""
      }))
      // Set current session's loading state
      setSessionLoadings(prev => ({
        ...prev,
        [sessionId]: true
      }))
    } catch (error) {
      console.error("Failed to send message:", error)
      setSessionLoadings(prev => ({
        ...prev,
        [sessionId]: false
      }))
    }
  }, [sendMessage])

  // Callback for ChatInput component - interrupt
  const handleInterrupt = useCallback((sessionId: string) => {
    try {
      // Send interrupt via global WebSocket
      interrupt(sessionId)
      setSessionLoadings(prev => ({
        ...prev,
        [sessionId]: false
      }))
    } catch (error) {
      console.error("Failed to interrupt session:", error)
    }
  }, [interrupt])

  // Callback for ChatInput component - track input changes
  const handleInputChange = useCallback((sessionId: string, value: string) => {
    setSessionInputs(prev => ({
      ...prev,
      [sessionId]: value
    }))
  }, [])

  const openCreateDialog = (nodeId: string) => {
    setSelectedNodeId(nodeId)
    setSessionMode(SessionMode.CHAT)
    setSessionModel(LLMModel.SONNET)
    setCreateDialogOpen(true)
  }

  const handleCreateSession = async () => {
    if (!selectedNodeId) return

    try {
      setCreating(true)
      const newSession = await apiClient.createSession(mosaicId, selectedNodeId, {
        mode: sessionMode,
        model: sessionModel,
      })

      console.log("[Chat] Session created via API, waiting for session_started notification for", newSession.session_id)

      // Wait for session_started notification before updating UI
      const started = await Promise.race([
        // Wait for session_started notification
        new Promise<boolean>((resolve) => {
          sessionStartedResolvers.current.set(newSession.session_id, resolve)
        }),
        // Timeout after 10 seconds
        new Promise<boolean>((resolve) =>
          setTimeout(() => {
            console.warn("[Chat] Timeout waiting for session_started notification")
            sessionStartedResolvers.current.delete(newSession.session_id)
            resolve(false)
          }, 10000)
        ),
      ])

      if (started) {
        console.log("[Chat] Session started successfully")
      } else {
        console.warn("[Chat] Session created but did not receive session_started notification in time")
        // Refresh session list even on timeout (in case notification was lost)
        await loadNodesAndSessions()
      }

      // Activate the new session and close dialog
      selectSession(newSession.session_id)
      setCreateDialogOpen(false)
    } catch (error) {
      console.error("Failed to create session:", error)
    } finally {
      setCreating(false)
    }
  }

  const toggleNode = (nodeId: string) => {
    setNodes((prev) =>
      prev.map((node) => {
        if (node.node_id === nodeId) {
          return { ...node, expanded: !node.expanded }
        }
        return node
      })
    )
  }

  // Toggle tree session expansion
  const toggleTreeSession = (sessionId: string) => {
    setTreeExpandedSessions((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(sessionId)) {
        newSet.delete(sessionId)
      } else {
        newSet.add(sessionId)
      }
      return newSet
    })
  }

  // Build session tree from flat session list
  const buildSessionTree = (sessions: SessionOut[]): SessionTreeNode[] => {
    const sessionMap = new Map<string, SessionTreeNode>()

    // Create tree nodes for all sessions
    sessions.forEach(session => {
      sessionMap.set(session.session_id, {
        ...session,
        children: [],
        depth: 0
      })
    })

    const roots: SessionTreeNode[] = []

    // Build parent-child relationships
    sessions.forEach(session => {
      const node = sessionMap.get(session.session_id)!
      if (session.parent_session_id) {
        const parent = sessionMap.get(session.parent_session_id)
        if (parent) {
          parent.children.push(node)
          node.depth = parent.depth + 1
        } else {
          // Parent not in current session list, treat as root
          roots.push(node)
        }
      } else {
        // No parent, this is a root session
        roots.push(node)
      }
    })

    return roots
  }

  // Cleanup terminal instance for a session
  const cleanupTerminalForSession = (sessionId: string) => {
    const terminalData = terminalsMapRef.current.get(sessionId)
    if (terminalData) {
      console.log('[Terminal] Cleaning up terminal for session:', sessionId)

      // Send terminal_stop to backend
      sendRaw({
        session_id: sessionId,
        type: 'terminal_stop'
      })

      // Dispose terminal instance if exists
      if (terminalData.terminal) {
        terminalData.terminal.dispose()
      }

      // Remove from map completely
      terminalsMapRef.current.delete(sessionId)

      // Clear current attached terminal ref if it's this session
      if (currentAttachedTerminalRef.current === sessionId) {
        currentAttachedTerminalRef.current = null
      }
    }
  }

  const handleArchiveSession = async (sessionId: string, nodeId: string) => {
    try {
      await apiClient.archiveSession(mosaicId, nodeId, sessionId)

      // Cleanup terminal instance for this session
      cleanupTerminalForSession(sessionId)

      // Remove from current list
      setNodes((prev) =>
        prev.map((node) => ({
          ...node,
          sessions: node.sessions.filter((s) => s.session_id !== sessionId),
        }))
      )

      // Clear input content for this session
      setSessionInputs(prev => {
        const newInputs = { ...prev }
        delete newInputs[sessionId]
        return newInputs
      })

      // If it was active, clear selection
      if (activeSessionId === sessionId) {
        selectSession(null)
      }
    } catch (error) {
      console.error("Failed to archive session:", error)
    }
  }

  const openBatchArchiveDialog = (nodeId: string) => {
    const node = nodes.find(n => n.node_id === nodeId)
    if (!node) return

    const closedSessions = node.sessions.filter(s => s.status === SessionStatus.CLOSED)
    if (closedSessions.length === 0) return

    setBatchArchivingNode({
      nodeId,
      closedSessionIds: closedSessions.map(s => s.session_id)
    })
    setBatchArchiveDialogOpen(true)
  }

  const handleBatchArchive = async () => {
    if (!batchArchivingNode) return

    try {
      setBatchArchiving(true)
      const result = await apiClient.batchArchiveSessions(mosaicId, batchArchivingNode.nodeId)

      // Cleanup terminal instances for all archived sessions
      batchArchivingNode.closedSessionIds.forEach(sessionId => {
        cleanupTerminalForSession(sessionId)
      })

      // Remove archived sessions from current list
      setNodes((prev) =>
        prev.map((node) => {
          if (node.node_id === batchArchivingNode.nodeId) {
            return {
              ...node,
              sessions: node.sessions.filter(
                (s) => !batchArchivingNode.closedSessionIds.includes(s.session_id)
              ),
            }
          }
          return node
        })
      )

      // Clear input content for archived sessions
      setSessionInputs(prev => {
        const newInputs = { ...prev }
        batchArchivingNode.closedSessionIds.forEach(sessionId => {
          delete newInputs[sessionId]
        })
        return newInputs
      })

      // If active session was archived, clear selection
      if (activeSessionId && batchArchivingNode.closedSessionIds.includes(activeSessionId)) {
        selectSession(null)
      }

      // Show result message
      if (result.failed_sessions.length > 0) {
        console.warn(`批量归档完成，但有 ${result.failed_sessions.length} 个会话失败`)
      }

      setBatchArchiveDialogOpen(false)
    } catch (error) {
      console.error("Failed to batch archive sessions:", error)
    } finally {
      setBatchArchiving(false)
    }
  }

  const openCloseDialog = (sessionId: string, nodeId: string) => {
    setClosingSession({ sessionId, nodeId })
    setCloseDialogOpen(true)
  }

  const handleCloseSession = async () => {
    if (!closingSession) return

    console.log("[Chat] Closing session:", closingSession.sessionId)

    try {
      setClosing(true)
      const updatedSession = await apiClient.closeSession(
        mosaicId,
        closingSession.nodeId,
        closingSession.sessionId
      )

      console.log("[Chat] Session closed successfully, updating local state")

      // Update session status in local state
      setNodes((prev) =>
        prev.map((node) => ({
          ...node,
          sessions: node.sessions.map((s) =>
            s.session_id === closingSession.sessionId ? { ...s, status: updatedSession.status } : s
          ),
        }))
      )

      console.log("[Chat] Local state updated, messages count:", messages.length)

      setCloseDialogOpen(false)
      setClosingSession(null)
    } catch (error) {
      console.error("Failed to close session:", error)
    } finally {
      setClosing(false)
    }
  }

  // Get current session and node status
  const getCurrentSession = () => {
    if (!activeSessionId) return null
    for (const node of nodes) {
      const session = node.sessions.find((s) => s.session_id === activeSessionId)
      if (session) {
        return { session, nodeStatus: node.status, nodeId: node.node_id }
      }
    }
    return null
  }

  const currentSessionInfo = getCurrentSession()
  const canSendMessage =
    currentSessionInfo &&
    currentSessionInfo.nodeStatus === NodeStatus.RUNNING &&
    currentSessionInfo.session.status === SessionStatus.ACTIVE

  const toggleThinkingCollapse = useCallback((messageId: string) => {
    setCollapsedMessages((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(messageId)) {
        newSet.delete(messageId)
      } else {
        newSet.add(messageId)
      }
      return newSet
    })
  }, [])


  // Handle copy session ID (referenced from sessions page)
  const handleCopySessionId = async (sessionId: string) => {
    console.log("handleCopySessionId called for:", sessionId)
    console.log("navigator.clipboard:", navigator.clipboard)
    console.log("window.isSecureContext:", window.isSecureContext)

    try {
      // Try modern clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        console.log("Using navigator.clipboard.writeText")
        await navigator.clipboard.writeText(sessionId)
        console.log("Copy successful via clipboard API")
        setCopiedSessionId(sessionId)
        setTimeout(() => setCopiedSessionId(null), 1000)
      } else {
        // Fallback for older browsers or non-secure contexts
        console.log("Using execCommand fallback")

        // Create and immediately append textarea
        const textArea = document.createElement("textarea")
        textArea.value = sessionId
        textArea.style.position = "fixed"
        textArea.style.left = "0"
        textArea.style.top = "0"
        textArea.style.width = "2em"
        textArea.style.height = "2em"
        textArea.style.padding = "0"
        textArea.style.border = "none"
        textArea.style.outline = "none"
        textArea.style.boxShadow = "none"
        textArea.style.background = "transparent"

        document.body.appendChild(textArea)

        // Store current selection
        const selected = document.getSelection()?.rangeCount ? document.getSelection()?.getRangeAt(0) : null

        // Select the textarea content
        textArea.select()
        textArea.setSelectionRange(0, textArea.value.length)

        // Execute copy command
        let successful = false
        try {
          successful = document.execCommand('copy')
          console.log("execCommand result:", successful)
        } catch (err) {
          console.error("execCommand error:", err)
        }

        // Restore previous selection
        if (selected) {
          document.getSelection()?.removeAllRanges()
          document.getSelection()?.addRange(selected)
        }

        document.body.removeChild(textArea)

        if (successful) {
          setCopiedSessionId(sessionId)
          setTimeout(() => setCopiedSessionId(null), 1000)
        } else {
          throw new Error("Copy command failed")
        }
      }
    } catch (error) {
      console.error("Copy failed:", error)
    }
  }

  // Session action menu component
  const SessionActionMenu = ({ session, nodeId }: { session: SessionOut; nodeId: string }) => {
    const handleCopy = () => {
      console.log("handleCopy triggered in SessionActionMenu")

      // 延迟执行复制操作，确保在菜单关闭后执行
      setTimeout(() => {
        console.log("Executing delayed copy operation")

        // Create a hidden input element
        const input = document.createElement("input")
        input.value = session.session_id
        input.style.position = "fixed"
        input.style.top = "0"
        input.style.left = "0"
        input.style.width = "2em"
        input.style.height = "2em"
        input.style.padding = "0"
        input.style.border = "none"
        input.style.outline = "none"
        input.style.boxShadow = "none"
        input.style.background = "transparent"
        input.setAttribute("readonly", "")

        document.body.appendChild(input)

        // Focus and select the input content
        input.focus()
        input.select()
        input.setSelectionRange(0, input.value.length)

        // Copy using execCommand
        let successful = false
        try {
          successful = document.execCommand('copy')
          console.log("execCommand result:", successful)

          if (successful) {
            console.log("Setting copiedSessionId to:", session.session_id)
            setCopiedSessionId(session.session_id)
            setTimeout(() => {
              console.log("Clearing copiedSessionId")
              setCopiedSessionId(null)
            }, 1000)
          } else {
            console.error("execCommand returned false")
          }
        } catch (err) {
          console.error("Copy error:", err)
        }

        document.body.removeChild(input)
        console.log("Copy operation completed")
      }, 100) // 100ms 延迟，足够菜单关闭
    }

    const handleClose = (e: Event) => {
      e.preventDefault()
      openCloseDialog(session.session_id, nodeId)
    }

    const handleArchive = (e: Event) => {
      e.preventDefault()
      handleArchiveSession(session.session_id, nodeId)
    }

    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreVertical className="h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem
            onSelect={(e) => {
              // 阻止默认的菜单关闭行为（如果需要）
              // e.preventDefault()
              handleCopy()
            }}
          >
            复制会话 ID
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {session.status === SessionStatus.ACTIVE && (
            <DropdownMenuItem onSelect={handleClose}>
              关闭会话
            </DropdownMenuItem>
          )}
          {session.status === SessionStatus.CLOSED && (
            <DropdownMenuItem onSelect={handleArchive}>
              归档会话
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  // Session tree node component (recursive)
  const SessionTreeNodeComponent = ({
    session,
    depth,
    onSelect,
    isLast = false,
  }: {
    session: SessionTreeNode
    depth: number
    onSelect: (sessionId: string) => void
    isLast?: boolean
  }) => {
    const isExpanded = treeExpandedSessions.has(session.session_id)
    const isActive = activeSessionId === session.session_id
    const hasChildren = session.child_count > 0

    return (
      <div>
        {/* Session item */}
        <div
          className={`group relative cursor-pointer hover:bg-muted/50 transition-colors ${
            isActive
              ? "bg-primary/10 border-l-3 border-l-primary"
              : "border-l-3 border-l-transparent"
          }`}
          onClick={() => onSelect(session.session_id)}
        >
          {/* Tree lines for children (not root) */}
          {depth > 0 && (
            <>
              {/* Vertical line */}
              <div
                className="absolute top-0 bottom-0 w-px bg-border"
                style={{ left: `${(depth - 1) * 16 + 16}px` }}
              >
                {isLast && <div className="absolute top-3 left-0 w-px h-full bg-background" />}
              </div>
              {/* Horizontal line */}
              <div
                className="absolute top-3 h-px bg-border"
                style={{
                  left: `${(depth - 1) * 16 + 16}px`,
                  width: '12px'
                }}
              />
            </>
          )}

          {sessionListMode === 'detailed' ? (
            /* Detailed mode */
            <div className="pr-3 py-2" style={{ paddingLeft: `${depth * 16 + 12}px` }}>
              {/* Line 1: Expand button + Root badge + Session ID + Status + Menu */}
              <div className="flex items-center gap-2 mb-1">
                {/* Expand/collapse button for sessions with children */}
                {hasChildren ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleTreeSession(session.session_id)
                    }}
                    className="shrink-0"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </button>
                ) : (
                  <div className="w-3.5" />
                )}

                {/* Root badge if no parent */}
                {!session.parent_session_id && (
                  <Badge variant="outline" className="text-xs h-5 px-1.5 shrink-0">
                    根
                  </Badge>
                )}

                <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span
                  className={`font-mono text-xs truncate ${
                    isActive ? "font-semibold" : "text-muted-foreground"
                  }`}
                  title={session.session_id}
                >
                  {session.session_id.slice(0, 8)}
                </span>
                <Badge
                  variant={
                    session.status === SessionStatus.ACTIVE
                      ? "default"
                      : "secondary"
                  }
                  className="text-xs h-5 px-1.5"
                >
                  {session.status === SessionStatus.ACTIVE && "活跃"}
                  {session.status === SessionStatus.CLOSED && "已关闭"}
                </Badge>
                <div className="ml-auto">
                  <SessionActionMenu session={session} nodeId={session.node_id} />
                </div>
              </div>

              {/* Line 2: Node ID + Mode + Model */}
              <div style={{ paddingLeft: hasChildren ? '14px' : '0px' }} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="text-amber-600 font-medium">{session.node_id}</span>
                <span>·</span>
                <span>{session.mode}</span>
                <span>·</span>
                <span>{session.model || 'sonnet'}</span>
              </div>
            </div>
          ) : (
            /* Compact mode */
            <div className="pr-3 py-1.5" style={{ paddingLeft: `${depth * 16 + 12}px` }}>
              <div className="flex items-center gap-2">
                {/* Expand/collapse button */}
                {hasChildren ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleTreeSession(session.session_id)
                    }}
                    className="shrink-0"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    )}
                  </button>
                ) : (
                  <div className="w-3" />
                )}

                {/* Root badge */}
                {!session.parent_session_id && (
                  <Badge variant="outline" className="text-xs h-4 px-1 shrink-0">
                    根
                  </Badge>
                )}

                <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />
                <span
                  className={`font-mono text-xs truncate ${
                    isActive ? "font-semibold" : "text-muted-foreground"
                  }`}
                  title={session.session_id}
                >
                  {session.session_id.slice(0, 8)}
                </span>
                <span className="text-xs text-amber-600 font-medium truncate">
                  {session.node_id}
                </span>
                <Circle
                  className={`h-1.5 w-1.5 shrink-0 ml-auto ${
                    session.status === SessionStatus.ACTIVE
                      ? 'fill-blue-500 text-blue-500'
                      : 'fill-gray-400 text-gray-400'
                  }`}
                />
                <div>
                  <SessionActionMenu session={session} nodeId={session.node_id} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Recursively render children */}
        {isExpanded && session.children.map((child, index) => (
          <SessionTreeNodeComponent
            key={child.session_id}
            session={child}
            depth={depth + 1}
            onSelect={onSelect}
            isLast={index === session.children.length - 1}
          />
        ))}
      </div>
    )
  }

  // Workspace functions
  // 懒加载目录子节点
  const loadDirectoryChildren = async (path: string, nodeId: string) => {
    try {
      const data = await apiClient.listWorkspaceFiles(mosaicId, nodeId, {
        path: path,
        recursive: false,
        max_depth: 1
      })

      // 将加载的数据转换为 FileNode
      const convertToFileNodes = (items: WorkspaceFileItem[]): FileNode[] => {
        return items.map(item => ({
          ...item,
          expanded: false,
          children: item.type === 'directory' ? undefined : undefined
        }))
      }

      return convertToFileNodes(data.items)
    } catch (error) {
      console.error(`Failed to load directory: ${path}`, error)
      return []
    }
  }

  const toggleDirectory = async (path: string) => {
    // 先找到目标节点，检查是否需要懒加载
    const findNode = (nodes: FileNode[]): FileNode | null => {
      for (const node of nodes) {
        if (node.path === path) return node
        if (node.children) {
          const found = findNode(node.children)
          if (found) return found
        }
      }
      return null
    }

    const targetNode = findNode(fileTree)

    // 如果是展开操作 且 children 未加载（undefined），则先加载数据
    if (targetNode && !targetNode.expanded && targetNode.children === undefined && currentSessionInfo) {
      const children = await loadDirectoryChildren(path, currentSessionInfo.nodeId)

      // 更新树：设置 children 并展开
      const updateTree = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(node => {
          if (node.path === path) {
            return { ...node, expanded: true, children }
          }
          if (node.children) {
            return { ...node, children: updateTree(node.children) }
          }
          return node
        })
      }
      setFileTree(updateTree(fileTree))
    } else {
      // 如果已有数据，只切换展开/折叠状态
      const toggleInTree = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(node => {
          if (node.path === path && node.type === 'directory') {
            return { ...node, expanded: !node.expanded }
          }
          if (node.children) {
            return { ...node, children: toggleInTree(node.children) }
          }
          return node
        })
      }
      setFileTree(toggleInTree(fileTree))
    }
  }

  const handleFileClick = async (path: string, nodeId: string) => {
    if (!nodeId) return

    try {
      setFileContentLoading(true)
      const data = await apiClient.getWorkspaceFileContent(mosaicId, nodeId, {
        path,
        encoding: 'utf-8',
        max_size: 1048576 // 1MB
      })

      setSelectedFile({
        path: data.path,
        content: data.content,
        language: data.language
      })
    } catch (error) {
      console.error("Failed to load file content:", error)
      setSelectedFile({
        path,
        content: `// Failed to load file: ${error}`,
        language: null
      })
    } finally {
      setFileContentLoading(false)
    }
  }

  const renderFileTree = (nodes: FileNode[], nodeId: string, level: number = 0) => {
    return nodes.map((node) => (
      <div key={node.path}>
        <div
          className={`flex items-center gap-2 px-2 py-1 hover:bg-muted/50 cursor-pointer ${
            selectedFile?.path === node.path ? 'bg-muted' : ''
          }`}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onClick={async () => {
            if (node.type === 'directory') {
              await toggleDirectory(node.path)
            } else {
              handleFileClick(node.path, nodeId)
            }
          }}
        >
          {node.type === 'directory' ? (
            <>
              {node.expanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              {node.expanded ? (
                <FolderOpen className="h-4 w-4 shrink-0 text-yellow-500" />
              ) : (
                <Folder className="h-4 w-4 shrink-0 text-yellow-500" />
              )}
            </>
          ) : (
            <>
              <span className="w-4 shrink-0" />
              {node.name.endsWith('.tsx') || node.name.endsWith('.ts') || node.name.endsWith('.jsx') || node.name.endsWith('.js') ? (
                <FileCode className="h-4 w-4 shrink-0 text-blue-500" />
              ) : node.name.endsWith('.json') ? (
                <FileText className="h-4 w-4 shrink-0 text-green-500" />
              ) : node.name.endsWith('.md') ? (
                <FileText className="h-4 w-4 shrink-0 text-purple-500" />
              ) : (
                <File className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
            </>
          )}
          <span className="text-sm whitespace-nowrap">{node.name}</span>
        </div>
        {node.type === 'directory' && node.expanded && node.children && (
          <div>{renderFileTree(node.children, nodeId, level + 1)}</div>
        )}
      </div>
    ))
  }

  return (
    <div className="flex absolute inset-0 overflow-hidden">
      {/* Mobile session list button - Fixed on right edge */}
      {isMobile && (
        <button
          onClick={() => setSessionSheetOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 z-40 bg-background/80 backdrop-blur border border-border rounded-l-md shadow-sm px-1.5 py-2 hover:bg-muted/80 transition-colors md:hidden flex items-center"
          style={{ writingMode: 'vertical-rl' }}
        >
          <span className="text-xs text-muted-foreground">会话列表</span>
        </button>
      )}

      {/* Middle: Main Content Area */}
      <div className="flex-1 flex flex-col bg-muted/20 min-w-0">
        {/* Tab Switcher + Header */}
        <div className="border-b bg-background flex items-center justify-between shrink-0 h-11 px-3 sm:px-4">
          {/* Left: Session info - Node and Session ID */}
          {viewMode === 'chat' ? (
            currentSessionInfo ? (
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {/* Node and Session ID */}
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-xs sm:text-sm font-mono text-muted-foreground truncate">
                    {currentSessionInfo.nodeId}
                    <span className="mx-1">/</span>
                    {activeSessionId?.slice(0, 8)}
                  </span>
                  {/* WebSocket status */}
                  {currentSessionInfo.session.status === SessionStatus.ACTIVE && (
                    <div
                      className={`h-2 w-2 rounded-full shrink-0 ${
                        isConnected ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                  )}
                </div>

                {/* Show badges only on desktop */}
                <div className="hidden sm:flex items-center gap-1.5">
                  <Badge variant="outline" className="text-xs shrink-0">
                    {currentSessionInfo.session.mode}
                  </Badge>
                  {currentSessionInfo.session.model && (
                    <Badge variant="outline" className="text-xs shrink-0">
                      {currentSessionInfo.session.model}
                    </Badge>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className="text-xs sm:text-sm text-muted-foreground truncate">
                  请选择会话
                </span>
              </div>
            )
          ) : (
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span className="text-xs sm:text-sm text-muted-foreground truncate">
                {currentSessionInfo ? `节点: ${currentSessionInfo.nodeId}` : '请选择会话'}
              </span>
            </div>
          )}

          {/* Right: Usage statistics and View mode toggle */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Usage statistics */}
            {sessionStats && currentSessionInfo && viewMode === 'chat' && (
              <div className="flex items-center gap-2 sm:gap-3 text-xs text-muted-foreground">
                {sessionStats.total_cost_usd !== undefined && (
                  <div className="flex items-center gap-1">
                    <span>💰</span>
                    <span className="font-mono">
                      ${sessionStats.total_cost_usd.toFixed(4)}
                    </span>
                  </div>
                )}
                {(sessionStats.total_input_tokens !== undefined ||
                  sessionStats.total_output_tokens !== undefined) && (
                  <div className="flex items-center gap-1">
                    <span>📊</span>
                    <span className="font-mono">
                      {sessionStats.total_input_tokens?.toLocaleString() || 0}↑
                      <span className="mx-0.5">/</span>
                      {sessionStats.total_output_tokens?.toLocaleString() || 0}↓
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* View mode toggle - Hidden on mobile */}
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs hidden sm:inline-flex"
              onClick={() => setViewMode(viewMode === 'chat' ? 'workspace' : 'chat')}
            >
              {viewMode === 'chat' ? '切换到工作区' : '切换到聊天区'}
            </Button>
          </div>
        </div>

        {/* Content Area - Switch between Chat and Workspace */}
        {viewMode === 'chat' ? (
          /* Chat View */
          !activeSessionId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground px-4">
                <MessageSquare className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
                <p className="text-sm sm:text-base">请选择一个会话</p>
              </div>
            </div>
          ) : !isConnected ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="h-6 w-6 sm:h-7 sm:w-7 md:h-8 md:w-8 animate-spin" />
              <span className="ml-2 text-sm sm:text-base">连接中...</span>
            </div>
          ) : (
            <>
              {/* Messages Area */}
              <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {currentLoading ? (
                    <div className="text-center">
                      <Loader2 className="h-8 w-8 sm:h-10 sm:w-10 md:h-12 md:w-12 animate-spin mx-auto mb-2" />
                      <p className="text-sm sm:text-base">正在加载消息...</p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <MessageSquare className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
                      <p className="text-sm sm:text-base">发送消息开始对话</p>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {messages.map((msg) => (
                    <MessageItem
                      key={msg.message_id}
                      message={msg}
                      isCollapsed={collapsedMessages.has(msg.message_id)}
                      onToggleCollapse={toggleThinkingCollapse}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input Area */}
            <ChatInput
              sessionId={activeSessionId}
              initialValue={currentInput}
              isLoading={currentLoading}
              isConnected={isConnected}
              canSendMessage={!!canSendMessage}
              placeholder={
                !currentSessionInfo
                  ? "请选择会话"
                  : currentSessionInfo.session.status === SessionStatus.CLOSED
                  ? "会话已关闭，只能查看内容"
                  : currentSessionInfo.nodeStatus !== NodeStatus.RUNNING
                  ? "节点未运行，无法发送消息"
                  : !isConnected
                  ? "WebSocket 连接中..."
                  : "输入消息... (Ctrl+Enter发送)"
              }
              onSendMessage={handleSendMessage}
              onInterrupt={handleInterrupt}
              onInputChange={handleInputChange}
            />
          </>
        )
        ) : (
          /* Workspace View */
          !activeSessionId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Folder className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
                <p className="text-sm sm:text-base px-4">请选择一个会话查看工作区</p>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex overflow-hidden">
              {/* Left: File Tree - Resizable & Collapsible */}
              <div
                className="bg-background overflow-hidden flex flex-col"
                style={{
                  width: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
                  minWidth: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
                  maxWidth: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
                  transition: sidebarCollapsed ? 'width 0.2s ease-in-out' : 'none',
                }}
              >
                {/* Header */}
                <div className="px-3 py-1.5 border-b bg-background flex items-center justify-between shrink-0">
                  {!sidebarCollapsed ? (
                    <>
                      <div className="flex items-center gap-2">
                        <Folder className="h-4 w-4" />
                        <span className="text-sm font-medium">文件树</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => currentSessionInfo && loadWorkspace(currentSessionInfo.nodeId)}
                          disabled={workspaceLoading}
                        >
                          <RefreshCw className={`h-3.5 w-3.5 ${workspaceLoading ? 'animate-spin' : ''}`} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={toggleSidebarCollapse}
                        >
                          <ChevronLeft className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 mx-auto"
                      onClick={toggleSidebarCollapse}
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>

                {/* File Tree Content */}
                {!sidebarCollapsed && (
                  <div className="py-2 overflow-auto flex-1">
                    {workspaceLoading ? (
                      <div className="p-4 text-center text-sm text-muted-foreground">
                        <Loader2 className="h-5 w-5 sm:h-6 sm:w-6 animate-spin mx-auto mb-2" />
                        <span className="text-xs sm:text-sm">加载中...</span>
                      </div>
                    ) : fileTree.length === 0 ? (
                      <div className="p-4 text-center text-xs sm:text-sm text-muted-foreground">
                        工作区为空
                      </div>
                    ) : (
                      currentSessionInfo && renderFileTree(fileTree, currentSessionInfo.nodeId)
                    )}
                  </div>
                )}
              </div>

              {/* Resize Handle - Draggable divider */}
              {!sidebarCollapsed && (
                <div
                  className="relative shrink-0 cursor-col-resize group"
                  onMouseDown={handleResizeStart}
                  style={{ width: '16px' }}
                >
                  <div
                    className="absolute left-1/2 top-0 bottom-0 -translate-x-1/2 w-px bg-border group-hover:w-0.5 group-hover:bg-muted-foreground/50"
                    style={{
                      width: isResizing ? '2px' : undefined,
                      backgroundColor: isResizing ? 'hsl(var(--muted-foreground) / 0.5)' : undefined,
                    }}
                  />
                </div>
              )}

              {/* Right: File Content Viewer & Terminal (Split Vertically) */}
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Top: File Content Viewer */}
                <div
                  className="flex flex-col bg-muted/20 overflow-hidden"
                  style={{
                    height: terminalCollapsed ? '100%' : `calc(100% - ${terminalHeight}px - 16px)`,
                  }}
                >
                  {fileContentLoading ? (
                    <div className="flex-1 flex items-center justify-center">
                      <div className="text-center text-muted-foreground">
                        <Loader2 className="h-8 w-8 sm:h-10 sm:w-10 md:h-12 md:w-12 animate-spin mx-auto mb-2" />
                        <p className="text-xs sm:text-sm">加载文件内容...</p>
                      </div>
                    </div>
                  ) : selectedFile ? (
                    <>
                      {/* File header */}
                      <div className="border-b bg-background px-2 sm:px-3 md:px-4 py-2 shrink-0">
                        <div className="flex items-center gap-2">
                          <FileCode className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-blue-500 shrink-0" />
                          <span className="text-xs sm:text-sm font-mono truncate">{selectedFile.path}</span>
                        </div>
                      </div>
                      {/* File content */}
                      <div className="flex-1 overflow-auto">
                        <pre className="p-2 sm:p-3 md:p-4 text-xs sm:text-sm font-mono">
                          <code>{selectedFile.content}</code>
                        </pre>
                      </div>
                    </>
                  ) : (
                    <div className="flex-1 flex items-center justify-center">
                      <div className="text-center text-muted-foreground px-4">
                        <FileText className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
                        <p className="text-sm sm:text-base">选择一个文件查看内容</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Terminal Resize Handle - Draggable divider */}
                {!terminalCollapsed && (
                  <div
                    className="relative shrink-0 cursor-row-resize group"
                    onMouseDown={handleTerminalResizeStart}
                    style={{ height: '16px' }}
                  >
                    <div
                      className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-px bg-border group-hover:h-0.5 group-hover:bg-muted-foreground/50"
                      style={{
                        height: isTerminalResizing ? '2px' : undefined,
                        backgroundColor: isTerminalResizing ? 'hsl(var(--muted-foreground) / 0.5)' : undefined,
                      }}
                    />
                  </div>
                )}

                {/* Bottom: Terminal Panel */}
                <div
                  className="bg-background overflow-hidden flex flex-col border-t"
                  style={{
                    height: terminalCollapsed ? '40px' : `${terminalHeight}px`,
                    minHeight: terminalCollapsed ? '40px' : `${terminalHeight}px`,
                    maxHeight: terminalCollapsed ? '40px' : `${terminalHeight}px`,
                    transition: terminalCollapsed ? 'height 0.2s ease-in-out' : 'none',
                  }}
                >
                  {/* Terminal Header */}
                  <div className="px-3 py-2 border-b bg-background flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                      <TerminalIcon className="h-4 w-4" />
                      <span className="text-sm font-medium">终端</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => {
                          if (activeSessionId) {
                            const terminalData = terminalsMapRef.current.get(activeSessionId)
                            if (terminalData) {
                              // 1. Stop the backend terminal process
                              console.log('[Terminal] Restarting terminal for session:', activeSessionId)
                              sendRaw({
                                session_id: activeSessionId,
                                type: 'terminal_stop'
                              })

                              // 2. Clear serialized content and display
                              terminalData.serializedContent = ''
                              if (terminalData.terminal) {
                                terminalData.terminal.clear()
                                terminalData.terminal.writeln('Terminal restarting...')
                              }

                              // 3. Restart terminal after a short delay
                              setTimeout(() => {
                                sendRaw({
                                  session_id: activeSessionId,
                                  type: 'terminal_start'
                                })

                                // Send initial newline to trigger bash prompt display
                                setTimeout(() => {
                                  sendRaw({
                                    session_id: activeSessionId,
                                    type: 'terminal_input',
                                    data: '\r'
                                  })
                                }, 200)
                              }, 100)
                            }
                          }
                        }}
                        title="Clear and restart terminal"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={toggleTerminalCollapse}
                      >
                        {terminalCollapsed ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Terminal Content - Always rendered but visibility controlled by CSS */}
                  <div
                    ref={terminalRef}
                    className="flex-1 overflow-hidden"
                    style={{
                      height: '100%',
                      width: '100%',
                      display: terminalCollapsed ? 'none' : 'block'
                    }}
                  />
                </div>
              </div>
            </div>
          )
        )}
      </div>

      {/* Right: Session List (desktop only) */}
      <div className="w-80 border-l flex-col bg-background hidden md:flex">
        {/* Header with view and mode toggle */}
        <div className="h-11 border-b px-3 flex items-center justify-between shrink-0">
          <span className="text-sm font-medium">会话</span>
          <div className="flex items-center gap-1">
            {/* View mode toggle (tree/grouped) */}
            <TooltipProvider>
              <div className="inline-flex rounded border p-0.5 gap-0.5">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant={sessionViewMode === 'tree' ? 'default' : 'ghost'}
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => setSessionViewMode('tree')}
                    >
                      <Network className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>树形视图</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant={sessionViewMode === 'grouped' ? 'default' : 'ghost'}
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => setSessionViewMode('grouped')}
                    >
                      <FolderTree className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>节点分组</TooltipContent>
                </Tooltip>
              </div>
            </TooltipProvider>

            {/* List mode toggle (detailed/compact) */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setSessionListMode(mode => mode === 'detailed' ? 'compact' : 'detailed')}
                  >
                    {sessionListMode === 'detailed' ? (
                      <LayoutList className="h-4 w-4" />
                    ) : (
                      <List className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {sessionListMode === 'detailed' ? '切换到紧凑模式' : '切换到详细模式'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Session tree */}
        <div
          className="flex-1 overflow-y-auto"
          style={{
            scrollbarWidth: 'thin',
            scrollbarColor: 'hsl(var(--border)) transparent'
          }}
        >
          {nodes.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>暂无 Claude Code 节点</p>
              <p className="text-xs mt-1">请先创建节点</p>
            </div>
          ) : sessionViewMode === 'tree' ? (
            /* Tree view */
            (() => {
              // Get all sessions from all nodes
              const allSessions = nodes.flatMap(node => node.sessions)
              // Build tree structure
              const treeRoots = buildSessionTree(allSessions)

              return treeRoots.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  <MessageSquare className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>暂无会话</p>
                </div>
              ) : (
                treeRoots.map((rootSession, index) => (
                  <SessionTreeNodeComponent
                    key={rootSession.session_id}
                    session={rootSession}
                    depth={0}
                    onSelect={selectSession}
                    isLast={index === treeRoots.length - 1}
                  />
                ))
              )
            })()
          ) : (
            /* Grouped view (current behavior) */
            nodes.map((node) => (
              <div key={node.node_id} className="border-b last:border-b-0">
                {/* Node header */}
                <div
                  className="px-3 py-2.5 bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                  onClick={() => toggleNode(node.node_id)}
                >
                  <div className="flex items-center gap-2">
                    {/* Expand/collapse icon */}
                    {node.expanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}

                    {/* Folder icon */}
                    <FolderTree className="h-4 w-4 shrink-0 text-amber-600" />

                    {/* Node name */}
                    <span
                      className="font-medium text-sm truncate flex-1 min-w-0"
                      title={node.node_id}
                    >
                      {node.node_id}
                    </span>

                    {/* Status indicator */}
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Circle
                            className={`h-2 w-2 shrink-0 ${
                              node.status === NodeStatus.RUNNING
                                ? 'fill-green-500 text-green-500'
                                : 'fill-gray-400 text-gray-400'
                            }`}
                          />
                        </TooltipTrigger>
                        <TooltipContent>
                          {node.status === NodeStatus.RUNNING ? '运行中' : '已停止'}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>

                    {/* Session count and buttons */}
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-xs text-muted-foreground">
                        {node.sessions.length}
                      </span>

                      {/* Batch archive button - only show if there are closed sessions */}
                      {(() => {
                        const closedCount = node.sessions.filter(s => s.status === SessionStatus.CLOSED).length
                        if (closedCount > 0) {
                          return (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0 text-orange-600 hover:text-orange-700 hover:bg-orange-100"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      openBatchArchiveDialog(node.node_id)
                                    }}
                                  >
                                    <Archive className="h-3.5 w-3.5" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  批量归档已关闭会话
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )
                        }
                        return null
                      })()}

                      {/* Create session button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={(e) => {
                          e.stopPropagation()
                          openCreateDialog(node.node_id)
                        }}
                        disabled={node.status !== NodeStatus.RUNNING || !isConnected}
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Sessions under this node */}
                {node.expanded && (
                  <div className="bg-background">
                    {node.sessions.length === 0 ? (
                      <div className="pl-8 pr-3 py-3 text-center text-xs text-muted-foreground">
                        暂无会话
                      </div>
                    ) : (
                      node.sessions.map((session, index) => {
                        const isLast = index === node.sessions.length - 1
                        const isActive = activeSessionId === session.session_id

                        return (
                          <div
                            key={session.session_id}
                            className={`group relative cursor-pointer hover:bg-muted/50 transition-colors ${
                              isActive
                                ? "bg-primary/10 border-l-3 border-l-primary"
                                : "border-l-3 border-l-transparent"
                            }`}
                            onClick={() => selectSession(session.session_id)}
                          >
                            {/* Tree line */}
                            <div className="absolute left-5 top-0 bottom-0 w-px bg-border">
                              {isLast && <div className="absolute top-3 left-0 w-px h-full bg-background" />}
                            </div>
                            <div className="absolute left-5 top-3 w-3 h-px bg-border" />

                            {sessionListMode === 'detailed' ? (
                              /* Detailed mode: Two-line layout */
                              <div className="pl-8 pr-3 py-2">
                                {/* Line 1: Session ID + Status + Menu */}
                                <div className="flex items-center gap-2 mb-1">
                                  <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                  <span
                                    className={`font-mono text-xs truncate ${
                                      isActive ? "font-semibold" : "text-muted-foreground"
                                    }`}
                                  >
                                    {session.session_id.slice(0, 8)}
                                  </span>
                                  <Badge
                                    variant={
                                      session.status === SessionStatus.ACTIVE
                                        ? "default"
                                        : "secondary"
                                    }
                                    className="text-xs h-5 px-1.5"
                                  >
                                    {session.status === SessionStatus.ACTIVE && "活跃"}
                                    {session.status === SessionStatus.CLOSED && "已关闭"}
                                  </Badge>
                                  <div className="ml-auto">
                                    <SessionActionMenu session={session} nodeId={node.node_id} />
                                  </div>
                                </div>

                                {/* Line 2: Mode · Model · Message count */}
                                <div className="pl-5 flex items-center gap-1.5 text-xs text-muted-foreground">
                                  <span>{session.mode}</span>
                                  <span>·</span>
                                  <span>{session.model || 'sonnet'}</span>
                                </div>
                              </div>
                            ) : (
                              /* Compact mode: Single line */
                              <div className="pl-8 pr-3 py-1.5">
                                <div className="flex items-center gap-2">
                                  <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />
                                  <span
                                    className={`font-mono text-xs truncate ${
                                      isActive ? "font-semibold" : "text-muted-foreground"
                                    }`}
                                  >
                                    {session.session_id.slice(0, 8)}
                                  </span>
                                  <Circle
                                    className={`h-1.5 w-1.5 shrink-0 ml-auto ${
                                      session.status === SessionStatus.ACTIVE
                                        ? 'fill-blue-500 text-blue-500'
                                        : 'fill-gray-400 text-gray-400'
                                    }`}
                                  />
                                  <div>
                                    <SessionActionMenu session={session} nodeId={node.node_id} />
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer statistics */}
        <div className="h-9 border-t px-3 flex items-center justify-between shrink-0 bg-muted/20">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>{nodes.length} 节点</span>
            <span>·</span>
            <span>{nodes.reduce((sum, node) => sum + node.sessions.length, 0)} 会话</span>
          </div>
          {isConnected ? (
            <Circle className="h-2 w-2 fill-green-500 text-green-500" />
          ) : (
            <Circle className="h-2 w-2 fill-red-500 text-red-500" />
          )}
        </div>
      </div>

      {/* Create Session Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-md max-h-[90vh] overflow-y-scroll">
          <DialogHeader>
            <DialogTitle>新建会话</DialogTitle>
            <DialogDescription>
              为节点 {selectedNodeId} 创建新的会话
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>会话模式</Label>
              <Select
                value={sessionMode}
                onValueChange={(value) => setSessionMode(value as SessionMode)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={SessionMode.CHAT}>
                    Chat - 交互式对话
                  </SelectItem>
                  <SelectItem value={SessionMode.PROGRAM}>
                    Program - 编程模式
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>模型</Label>
              <Select
                value={sessionModel}
                onValueChange={(value) => setSessionModel(value as LLMModel)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={LLMModel.SONNET}>Sonnet</SelectItem>
                  <SelectItem value={LLMModel.OPUS}>Opus</SelectItem>
                  <SelectItem value={LLMModel.HAIKU}>Haiku</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreateSession} disabled={creating}>
              {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Close Session Confirmation Dialog */}
      <Dialog open={closeDialogOpen} onOpenChange={setCloseDialogOpen}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>确认关闭会话？</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-4">
            <p className="text-sm text-muted-foreground">
              确定要关闭会话 <span className="font-semibold text-foreground font-mono">{closingSession?.sessionId.slice(0, 8)}</span> 吗？
            </p>
            <p className="text-sm text-amber-600 font-medium">
              ⚠️ 警告：关闭后无法再发送消息，且无法重新开启。
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCloseDialogOpen(false)}
              disabled={closing}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleCloseSession}
              disabled={closing}
            >
              {closing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  关闭中...
                </>
              ) : (
                "确认关闭"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Batch Archive Confirmation Dialog */}
      <Dialog open={batchArchiveDialogOpen} onOpenChange={setBatchArchiveDialogOpen}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>批量归档会话</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-4">
            <p className="text-sm text-muted-foreground">
              确定要归档 <span className="font-semibold text-foreground">{batchArchivingNode?.nodeId}</span> 节点下的{" "}
              <span className="font-semibold text-foreground">{batchArchivingNode?.closedSessionIds.length}</span>{" "}
              个已关闭会话吗？
            </p>
            {batchArchivingNode && batchArchivingNode.closedSessionIds.length > 0 && (
              <div className="bg-muted/50 rounded-md p-3 space-y-1">
                <p className="text-xs font-medium text-muted-foreground mb-2">会话列表：</p>
                {batchArchivingNode.closedSessionIds.slice(0, 5).map((sessionId) => (
                  <p key={sessionId} className="text-xs font-mono text-muted-foreground">
                    • {sessionId.slice(0, 8)}
                  </p>
                ))}
                {batchArchivingNode.closedSessionIds.length > 5 && (
                  <p className="text-xs text-muted-foreground">
                    ... 等 {batchArchivingNode.closedSessionIds.length - 5} 个会话
                  </p>
                )}
              </div>
            )}
            <p className="text-sm text-muted-foreground">
              归档后这些会话将不再显示在列表中。
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setBatchArchiveDialogOpen(false)}
              disabled={batchArchiving}
            >
              取消
            </Button>
            <Button
              variant="default"
              onClick={handleBatchArchive}
              disabled={batchArchiving}
              className="bg-orange-600 hover:bg-orange-700"
            >
              {batchArchiving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  归档中...
                </>
              ) : (
                "确认归档"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Mobile Session List Sheet */}
      <Sheet open={sessionSheetOpen} onOpenChange={setSessionSheetOpen}>
        <SheetContent side="right" className="p-0 w-[85vw] sm:w-96" showClose={false}>
          <div className="flex h-full w-full flex-col bg-background relative">
            {/* Mobile Close Button */}
            <button
              onClick={() => setSessionSheetOpen(false)}
              className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 z-50 rounded-full bg-background border shadow-md p-2 hover:bg-accent transition-colors"
              aria-label="关闭会话列表"
            >
              <ChevronRight className="h-4 w-4" />
            </button>

          <SheetHeader className="h-11 border-b px-3 flex flex-row items-center justify-between shrink-0">
            <SheetTitle className="text-sm font-medium">会话</SheetTitle>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setSessionListMode(mode => mode === 'detailed' ? 'compact' : 'detailed')}
                  >
                    {sessionListMode === 'detailed' ? (
                      <LayoutList className="h-4 w-4" />
                    ) : (
                      <List className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {sessionListMode === 'detailed' ? '切换到紧凑模式' : '切换到详细模式'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </SheetHeader>

          {/* Session tree */}
          <div
            className="flex-1 overflow-y-auto"
            style={{
              scrollbarWidth: 'thin',
              scrollbarColor: 'hsl(var(--border)) transparent'
            }}
          >
            {nodes.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>暂无 Claude Code 节点</p>
                <p className="text-xs mt-1">请先创建节点</p>
              </div>
            ) : (
              nodes.map((node) => (
                <div key={node.node_id} className="border-b last:border-b-0">
                  {/* Node header */}
                  <div
                    className="px-3 py-2.5 bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                    onClick={() => toggleNode(node.node_id)}
                  >
                    <div className="flex items-center gap-2">
                      {/* Expand/collapse icon */}
                      {node.expanded ? (
                        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                      )}

                      {/* Folder icon */}
                      <FolderTree className="h-4 w-4 shrink-0 text-amber-600" />

                      {/* Node name */}
                      <span
                        className="font-medium text-sm truncate flex-1 min-w-0"
                        title={node.node_id}
                      >
                        {node.node_id}
                      </span>

                      {/* Status indicator */}
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Circle
                              className={`h-2 w-2 shrink-0 ${
                                node.status === NodeStatus.RUNNING
                                  ? 'fill-green-500 text-green-500'
                                  : 'fill-gray-400 text-gray-400'
                              }`}
                            />
                          </TooltipTrigger>
                          <TooltipContent>
                            {node.status === NodeStatus.RUNNING ? '运行中' : '已停止'}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>

                      {/* Session count and buttons */}
                      <div className="flex items-center gap-1 shrink-0">
                        <span className="text-xs text-muted-foreground">
                          {node.sessions.length}
                        </span>

                        {/* Batch archive button - only show if there are closed sessions */}
                        {(() => {
                          const closedCount = node.sessions.filter(s => s.status === SessionStatus.CLOSED).length
                          if (closedCount > 0) {
                            return (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-6 w-6 p-0 text-orange-600 hover:text-orange-700 hover:bg-orange-100"
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        openBatchArchiveDialog(node.node_id)
                                        setSessionSheetOpen(false)
                                      }}
                                    >
                                      <Archive className="h-3.5 w-3.5" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    批量归档已关闭会话
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            )
                          }
                          return null
                        })()}

                        {/* Create session button */}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={(e) => {
                            e.stopPropagation()
                            openCreateDialog(node.node_id)
                            setSessionSheetOpen(false)
                          }}
                          disabled={node.status !== NodeStatus.RUNNING || !isConnected}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Sessions under this node */}
                  {node.expanded && (
                    <div className="bg-background">
                      {node.sessions.length === 0 ? (
                        <div className="pl-8 pr-3 py-3 text-center text-xs text-muted-foreground">
                          暂无会话
                        </div>
                      ) : (
                        node.sessions.map((session, index) => {
                          const isLast = index === node.sessions.length - 1
                          const isActive = activeSessionId === session.session_id

                          return (
                            <div
                              key={session.session_id}
                              className={`group relative cursor-pointer hover:bg-muted/50 transition-colors ${
                                isActive
                                  ? "bg-primary/10 border-l-3 border-l-primary"
                                  : "border-l-3 border-l-transparent"
                              }`}
                              onClick={() => {
                                selectSession(session.session_id)
                                setSessionSheetOpen(false)
                              }}
                            >
                              {/* Tree line */}
                              <div className="absolute left-5 top-0 bottom-0 w-px bg-border">
                                {isLast && <div className="absolute top-3 left-0 w-px h-full bg-background" />}
                              </div>
                              <div className="absolute left-5 top-3 w-3 h-px bg-border" />

                              {sessionListMode === 'detailed' ? (
                                /* Detailed mode: Two-line layout */
                                <div className="pl-8 pr-3 py-2">
                                  {/* Line 1: Session ID + Status + Menu */}
                                  <div className="flex items-center gap-2 mb-1">
                                    <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                    <span
                                      className={`font-mono text-xs truncate ${
                                        isActive ? "font-semibold" : "text-muted-foreground"
                                      }`}
                                    >
                                      {session.session_id.slice(0, 8)}
                                    </span>
                                    <Badge
                                      variant={
                                        session.status === SessionStatus.ACTIVE
                                          ? "default"
                                          : "secondary"
                                      }
                                      className="text-xs h-5 px-1.5"
                                    >
                                      {session.status === SessionStatus.ACTIVE && "活跃"}
                                      {session.status === SessionStatus.CLOSED && "已关闭"}
                                    </Badge>
                                    <div className="ml-auto">
                                      <SessionActionMenu session={session} nodeId={node.node_id} />
                                    </div>
                                  </div>

                                  {/* Line 2: Mode · Model · Message count */}
                                  <div className="pl-5 flex items-center gap-1.5 text-xs text-muted-foreground">
                                    <span>{session.mode}</span>
                                    <span>·</span>
                                    <span>{session.model || 'sonnet'}</span>
                                  </div>
                                </div>
                              ) : (
                                /* Compact mode: Single line */
                                <div className="pl-8 pr-3 py-1.5">
                                  <div className="flex items-center gap-2">
                                    <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />
                                    <span
                                      className={`font-mono text-xs truncate ${
                                        isActive ? "font-semibold" : "text-muted-foreground"
                                      }`}
                                    >
                                      {session.session_id.slice(0, 8)}
                                    </span>
                                    <Circle
                                      className={`h-1.5 w-1.5 shrink-0 ml-auto ${
                                        session.status === SessionStatus.ACTIVE
                                          ? 'fill-blue-500 text-blue-500'
                                          : 'fill-gray-400 text-gray-400'
                                      }`}
                                    />
                                    <div>
                                      <SessionActionMenu session={session} nodeId={node.node_id} />
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Footer statistics */}
          <div className="h-9 border-t px-3 flex items-center justify-between shrink-0 bg-muted/20">
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>{nodes.length} 节点</span>
              <span>·</span>
              <span>{nodes.reduce((sum, node) => sum + node.sessions.length, 0)} 会话</span>
            </div>
            {isConnected ? (
              <Circle className="h-2 w-2 fill-green-500 text-green-500" />
            ) : (
              <Circle className="h-2 w-2 fill-red-500 text-red-500" />
            )}
          </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
