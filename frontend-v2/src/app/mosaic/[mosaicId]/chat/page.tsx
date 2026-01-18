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
  ArrowUp,
  ArrowDown,
  Coins,
  BarChart3,
  Play,
  Square,
  Power,
  Code2,
  Copy,
  Check,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { useWebSocket } from "@/contexts/websocket-context"
import { useVoiceInput } from "@/hooks/use-voice-input"
import {
  SessionMode,
  SessionStatus,
  RuntimeStatus,
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
import { ChatSession } from "./components/ChatSession"
import { WorkspaceView } from "./components/WorkspaceView"

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

// Circular progress component for context usage
const CircularProgress = memo(({ percentage }: { percentage: number }) => {
  // Determine color based on percentage (lighter versions)
  const getColor = () => {
    if (percentage < 60) return 'rgba(34, 197, 94, 0.4)' // green-500 with 40% opacity
    if (percentage < 85) return 'rgba(234, 179, 8, 0.4)' // yellow-500 with 40% opacity
    if (percentage < 95) return 'rgba(249, 115, 22, 0.4)' // orange-500 with 40% opacity
    return 'rgba(239, 68, 68, 0.5)' // red-500 with 50% opacity (slightly more visible when critical)
  }

  const color = getColor()
  const circumference = 2 * Math.PI * 15.9155
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <svg className="h-4 w-4 -rotate-90" viewBox="0 0 36 36">
      {/* Background circle - highly visible */}
      <circle
        cx="18"
        cy="18"
        r="15.9155"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        className="text-muted"
      />
      {/* Progress circle - lighter color */}
      <circle
        cx="18"
        cy="18"
        r="15.9155"
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
      />
    </svg>
  )
})

CircularProgress.displayName = 'CircularProgress'

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
  // Initialize as null - will be validated and set after loading nodes
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  // Lazy-loaded sessions (懒加载会话集合)
  const [loadedSessions, setLoadedSessions] = useState<Set<string>>(new Set())

  // Input state - Store input per session to preserve content when switching sessions
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

  // Session statistics - Store stats per session
  const [sessionStats, setSessionStats] = useState<Record<string, {
    total_cost_usd?: number
    total_input_tokens?: number
    total_output_tokens?: number
    context_usage?: number
    context_percentage?: number
  } | null>>({})

  // Session scroll states - Store scroll position and auto-scroll state per session
  const [sessionScrollStates, setSessionScrollStates] = useState<Record<string, {
    scrollTop: number
    autoScrollEnabled: boolean
  }>>({})

  // Get current active session stats
  const currentStats = activeSessionId ? sessionStats[activeSessionId] : null

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

  // Node control state - Track which nodes are being started/stopped
  const [nodeControlLoading, setNodeControlLoading] = useState<Record<string, boolean>>({})

  // Code-server state - Per node (simplified)
  const [nodeCodeServerUrl, setNodeCodeServerUrl] = useState<Record<string, string | null>>({})
  const [copiedCodeServerUrl, setCopiedCodeServerUrl] = useState<string | null>(null)

  // Notification state - Store notification enabled state
  const [notificationEnabled, setNotificationEnabled] = useState(() => {
    if (typeof window === 'undefined') return true // Default enabled
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-notification-enabled`)
      return saved !== 'false' // Default enabled if not set
    } catch (error) {
      console.error('[ChatPage] Failed to load notification setting:', error)
      return true
    }
  })

  // Refs
  const sessionStartedResolvers = useRef<Map<string, (value: boolean) => void>>(new Map())

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
        } else if (savedSessionId) {
          // Saved session is invalid (archived or deleted), clean up localStorage
          console.log('[ChatPage] Saved session no longer available, cleaning up localStorage:', savedSessionId)
          if (typeof window !== 'undefined') {
            try {
              localStorage.removeItem(`mosaic-${mosaicId}-active-session`)
            } catch (error) {
              console.error('[ChatPage] Failed to clean up localStorage:', error)
            }
          }

          // Select a new session
          const activeSession = allSessions.find((s) => s.status === SessionStatus.ACTIVE)
          if (activeSession) {
            targetSessionId = activeSession.session_id
            shouldSetSession = true
          } else if (allSessions.length > 0) {
            // If no active session, select first one (to view history)
            targetSessionId = allSessions[0].session_id
            shouldSetSession = true
          }
        } else if (!activeSessionId) {
          // 3. No saved session, only select if no session is currently active
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

  // Node control functions
  const handleStartNode = useCallback(async (nodeId: string) => {
    try {
      setNodeControlLoading(prev => ({ ...prev, [nodeId]: true }))
      await apiClient.startNode(mosaicId, nodeId)

      // Refresh nodes and sessions to get updated status
      await loadNodesAndSessions(false)
      console.log('[ChatPage] Node started:', nodeId)
    } catch (error) {
      console.error('[ChatPage] Failed to start node:', error)
    } finally {
      setNodeControlLoading(prev => ({ ...prev, [nodeId]: false }))
    }
  }, [mosaicId, loadNodesAndSessions])

  const handleStopNode = useCallback(async (nodeId: string) => {
    try {
      setNodeControlLoading(prev => ({ ...prev, [nodeId]: true }))
      await apiClient.stopNode(mosaicId, nodeId)

      // Refresh nodes and sessions to get updated status
      await loadNodesAndSessions(false)
      console.log('[ChatPage] Node stopped:', nodeId)
    } catch (error) {
      console.error('[ChatPage] Failed to stop node:', error)
    } finally {
      setNodeControlLoading(prev => ({ ...prev, [nodeId]: false }))
    }
  }, [mosaicId, loadNodesAndSessions])

  // Code-server control functions

  const handleCopyCodeServerUrl = useCallback(async (nodeId: string) => {
    const url = nodeCodeServerUrl[nodeId]
    if (!url) return

    try {
      await navigator.clipboard.writeText(url)
      setCopiedCodeServerUrl(nodeId)
      setTimeout(() => setCopiedCodeServerUrl(null), 2000)
    } catch (error) {
      console.error('[ChatPage] Failed to copy code-server URL:', error)
    }
  }, [nodeCodeServerUrl])

  // Show desktop/browser notification for new result messages
  const showNotification = useCallback((message: any) => {
    // Check if notifications are enabled
    if (!notificationEnabled) {
      return
    }

    // Check if browser supports notifications and permission is granted
    if (!('Notification' in window) || Notification.permission !== 'granted') {
      return
    }

    // Find session information
    const sessionInfo = nodes
      .flatMap((node) =>
        node.sessions.map((session) => ({
          nodeId: node.node_id,
          session,
        }))
      )
      .find((info) => info.session.session_id === message.session_id)

    if (!sessionInfo) return

    // Create notification title and body
    // Use topic if available, otherwise use full session_id
    const sessionName = sessionInfo.session.topic || message.session_id
    const title = 'Mosaic - 新消息'
    const body = `${sessionInfo.nodeId} / ${sessionName}\n收到新的响应消息`

    // Create notification
    // Use message_id as tag to ensure each message gets its own notification
    // If no message_id, use timestamp to make it unique
    const notificationTag = message.message_id || `${message.session_id}-${Date.now()}`
    const notification = new Notification(title, {
      body,
      icon: '/favicon.ico',
      tag: notificationTag, // Each message gets its own notification
      requireInteraction: false, // Auto-dismiss
      silent: false, // Allow sound
    })

    // Click notification to switch to the session
    notification.onclick = () => {
      window.focus()
      selectSession(message.session_id)
      notification.close()
    }

    console.log('[ChatPage] Notification shown for session:', message.session_id)
  }, [notificationEnabled, nodes, selectSession])

  // Mobile detection effect
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Save notification enabled state to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(
        `mosaic-${mosaicId}-notification-enabled`,
        notificationEnabled.toString()
      )
    } catch (error) {
      console.error('[ChatPage] Failed to save notification setting:', error)
    }
  }, [notificationEnabled, mosaicId])

  // Request notification permission on mount
  useEffect(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) return

    // Only request if permission hasn't been determined yet
    if (Notification.permission === 'default') {
      console.log('[ChatPage] Requesting notification permission...')
      Notification.requestPermission().then(permission => {
        console.log('[ChatPage] Notification permission:', permission)
      })
    } else {
      console.log('[ChatPage] Notification permission already:', Notification.permission)
    }
  }, [])

  // Load nodes and sessions on mount
  useEffect(() => {
    if (!token) return
    loadNodesAndSessions()
  }, [token, loadNodesAndSessions])

  // Lazy-load sessions: add to loadedSessions when activeSessionId changes
  useEffect(() => {
    if (activeSessionId && !loadedSessions.has(activeSessionId)) {
      console.log('[ChatPage] Lazy-loading session:', activeSessionId)
      setLoadedSessions(prev => new Set(prev).add(activeSessionId))
    }
  }, [activeSessionId, loadedSessions])

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
        if (wsMessage.message_type === "topic_updated") {
          console.log("[Chat] Topic updated, refreshing session list")
          loadNodesAndSessions(false) // Don't auto-select session
        }
        if (wsMessage.message_type === "runtime_status_changed") {
          console.log("[Chat] Runtime status changed, refreshing session list")
          loadNodesAndSessions(false) // Don't auto-select session
        }
      }

      // Handle assistant result messages - Show notification for all sessions
      if (wsMessage.role === "assistant" && wsMessage.message_type === "assistant_result") {
        console.log("[Chat] Received assistant result:", wsMessage.session_id)
        // Show notification for all sessions (including currently active one)
        showNotification(wsMessage)
      }
    })

    return () => {
      unsubscribe()
    }
  }, [subscribe, loadNodesAndSessions, showNotification])

  // Scroll and message loading logic removed - now handled by ChatSession component

  // Old WebSocket subscription logic removed - now handled by ChatSession component

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

  // Message tracking and scroll logic removed - now handled by ChatSession component

  // Cleanup pending session_started resolvers on unmount
  useEffect(() => {
    return () => {
      sessionStartedResolvers.current.clear()
    }
  }, [])
  // loadMessages removed - now handled by ChatSession component
  // loadWorkspace removed - now handled by WorkspaceView component
  // handleSendMessage removed - now handled by ChatSession component
  // handleInterrupt removed - now handled by ChatSession component

  // Callback for ChatInput component - track input changes
  const handleInputChange = useCallback((sessionId: string, value: string) => {
    setSessionInputs(prev => ({
      ...prev,
      [sessionId]: value
    }))
  }, [])

  // Callback for ChatSession component - track session statistics
  const handleStatsUpdate = useCallback((sessionId: string, stats: {
    total_cost_usd?: number
    total_input_tokens?: number
    total_output_tokens?: number
    context_usage?: number
    context_percentage?: number
  } | null) => {
    setSessionStats(prev => ({
      ...prev,
      [sessionId]: stats
    }))
  }, [])

  // Callback for ChatSession component - track session scroll state
  const handleScrollStateChange = useCallback((sessionId: string, state: {
    scrollTop: number
    autoScrollEnabled: boolean
  }) => {
    setSessionScrollStates(prev => ({
      ...prev,
      [sessionId]: state
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

  // cleanupTerminalForSession removed - now handled by WorkspaceView component

  const handleArchiveSession = async (sessionId: string, nodeId: string) => {
    try {
      await apiClient.archiveSession(mosaicId, nodeId, sessionId)

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

  // Load code-server URL when switching to workspace view
  useEffect(() => {
    const loadCodeServerUrl = async (nodeId: string) => {
      try {
        const result = await apiClient.getCodeServerUrl(mosaicId, nodeId)
        setNodeCodeServerUrl(prev => ({ ...prev, [nodeId]: result.url }))
        console.log('[ChatPage] Code-server URL loaded:', result.url)
      } catch (error) {
        console.error('[ChatPage] Failed to load code-server URL:', error)
      }
    }

    if (viewMode === 'workspace' && currentSessionInfo?.nodeId) {
      loadCodeServerUrl(currentSessionInfo.nodeId)
    }
  }, [viewMode, mosaicId, currentSessionInfo?.nodeId])

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
          {/* Tree lines for children (not root) - VSCode style */}
          {depth > 0 && (
            <>
              {/* Vertical line */}
              <div
                className="absolute top-0 bottom-0 w-px bg-muted-foreground/30"
                style={{ left: `${(depth - 1) * 16 + 16}px` }}
              >
                {isLast && <div className="absolute top-5 left-0 w-px h-full bg-background" />}
              </div>
              {/* Horizontal line */}
              <div
                className="absolute top-5 h-px bg-muted-foreground/30"
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

                <span
                  className={`font-mono text-xs truncate ${
                    isActive ? "font-semibold" : "text-muted-foreground"
                  }`}
                  title={session.topic || session.session_id}
                >
                  {session.topic || session.session_id.slice(0, 8)}
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

                <span
                  className={`font-mono text-xs truncate ${
                    isActive ? "font-semibold" : "text-muted-foreground"
                  }`}
                  title={session.topic || session.session_id}
                >
                  {session.topic || session.session_id.slice(0, 8)}
                </span>
                <span className="text-xs text-amber-600 font-medium truncate">
                  {session.node_id}
                </span>
                <Circle
                  className={`h-1.5 w-1.5 shrink-0 ml-auto ${
                    session.status === SessionStatus.ACTIVE && session.runtime_status === RuntimeStatus.IDLE
                      ? 'fill-green-500 text-green-500'
                      : session.status === SessionStatus.ACTIVE && session.runtime_status === RuntimeStatus.BUSY
                      ? 'fill-orange-500 text-orange-500'
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
                    {currentSessionInfo.session.topic || activeSessionId?.slice(0, 8)}
                  </span>
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
            <div className="flex items-center gap-3 min-w-0 flex-1">
              {/* Node ID */}
              <span className="text-xs sm:text-sm text-muted-foreground truncate">
                {currentSessionInfo ? `节点: ${currentSessionInfo.nodeId}` : '请选择会话'}
              </span>
            </div>
          )}

          {/* Right: View mode toggle */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Copy Code-Server URL button (workspace mode only) */}
            {viewMode === 'workspace' && currentSessionInfo && (() => {
              const nodeId = currentSessionInfo.nodeId
              const url = nodeCodeServerUrl[nodeId]
              const isCopied = copiedCodeServerUrl === nodeId

              return url ? (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCopyCodeServerUrl(nodeId)}
                        className="h-7 text-xs"
                      >
                        {isCopied ? (
                          <Check className="h-3.5 w-3.5 mr-1.5 text-green-600" />
                        ) : (
                          <Copy className="h-3.5 w-3.5 mr-1.5" />
                        )}
                        {isCopied ? '已复制' : '复制地址'}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      复制 Code-Server 地址到剪贴板
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ) : null
            })()}

            {/* Usage statistics */}
            {viewMode === 'chat' && currentStats && (
              <div className="hidden lg:flex items-center gap-3 text-xs text-muted-foreground border-r pr-3">
                {/* Cost */}
                {currentStats.total_cost_usd !== undefined && (
                  <div className="flex items-center gap-1">
                    <Coins className="h-3.5 w-3.5" />
                    <span className="font-mono">${currentStats.total_cost_usd.toFixed(2)}</span>
                  </div>
                )}
                {/* Tokens: Input / Output */}
                {(currentStats.total_input_tokens !== undefined || currentStats.total_output_tokens !== undefined) && (
                  <div className="flex items-center gap-1">
                    <BarChart3 className="h-3.5 w-3.5" />
                    {currentStats.total_input_tokens !== undefined && (
                      <>
                        <span className="font-mono">{currentStats.total_input_tokens.toLocaleString()}</span>
                        <ArrowUp className="h-3 w-3" />
                      </>
                    )}
                    {currentStats.total_input_tokens !== undefined && currentStats.total_output_tokens !== undefined && (
                      <span className="mx-0.5">/</span>
                    )}
                    {currentStats.total_output_tokens !== undefined && (
                      <>
                        <span className="font-mono">{currentStats.total_output_tokens.toLocaleString()}</span>
                        <ArrowDown className="h-3 w-3" />
                      </>
                    )}
                  </div>
                )}
                {/* Context Window Usage */}
                {(currentStats.context_usage !== undefined && currentStats.context_percentage !== undefined && currentStats.context_percentage > 0) && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="flex items-center gap-1">
                          <CircularProgress percentage={currentStats.context_percentage} />
                          <span className="font-mono">{currentStats.context_percentage.toFixed(1)}%</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="space-y-1">
                          <div className="font-semibold">Context Window Usage</div>
                          <div className="text-xs space-y-0.5">
                            <div>Used: {currentStats.context_usage.toLocaleString()} / 200,000 tokens</div>
                            <div>Percentage: {currentStats.context_percentage.toFixed(2)}%</div>
                          </div>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
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
          /* Chat View - Lazy-loaded sessions */
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
            /* Render all loaded ChatSession instances */
            <>
              {Array.from(loadedSessions).map(sessionId => (
                <ChatSession
                  key={sessionId}
                  sessionId={sessionId}
                  isVisible={sessionId === activeSessionId}
                  mosaicId={mosaicId}
                  nodes={nodes}
                  onInputChange={handleInputChange}
                  sessionInput={sessionInputs[sessionId] || ""}
                  onStatsUpdate={handleStatsUpdate}
                  onScrollStateChange={(state) => handleScrollStateChange(sessionId, state)}
                  initialScrollState={sessionScrollStates[sessionId]}
                />
              ))}
            </>
          )
        ) : (
          /* Workspace View - Lazy-loaded */
          !activeSessionId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Folder className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
                <p className="text-sm sm:text-base px-4">请选择一个会话查看工作区</p>
              </div>
            </div>
          ) : (
            /* Render WorkspaceView for each loaded session */
            <>
              {Array.from(loadedSessions).map(sessionId => {
                const sessionInfo = nodes
                  .flatMap((node) =>
                    node.sessions.map((session) => ({
                      nodeId: node.node_id,
                      session,
                    }))
                  )
                  .find((info) => info.session.session_id === sessionId)

                return sessionInfo ? (
                  <WorkspaceView
                    key={sessionId}
                    sessionId={sessionId}
                    nodeId={sessionInfo.nodeId}
                    mosaicId={mosaicId}
                    isVisible={sessionId === activeSessionId}
                    codeServerUrl={nodeCodeServerUrl[sessionInfo.nodeId] || null}
                  />
                ) : null
              })}
            </>
          )
        )}
      </div>

      {/* Right: Session List (desktop only) */}
      <div className="w-80 border-l flex-col bg-background hidden md:flex">
        {/* Header with view and mode toggle */}
        <div className="h-11 border-b px-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">会话列表</span>
            {/* Connection status indicator */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div>
                    <Circle className={`h-2 w-2 ${isConnected ? 'fill-green-500 text-green-500' : 'fill-red-500 text-red-500'}`} />
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  {isConnected ? 'WebSocket 已连接' : 'WebSocket 已断开'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
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

                    {/* Node name */}
                    <span
                      className="font-medium text-sm truncate flex-1 min-w-0"
                      title={node.node_id}
                    >
                      {node.node_id}
                    </span>

                    {/* Node control buttons */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      {/* Start/Stop node button */}
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={(e) => {
                                e.stopPropagation()
                                if (node.status === NodeStatus.RUNNING) {
                                  handleStopNode(node.node_id)
                                } else {
                                  handleStartNode(node.node_id)
                                }
                              }}
                              disabled={nodeControlLoading[node.node_id]}
                            >
                              {nodeControlLoading[node.node_id] ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : node.status === NodeStatus.RUNNING ? (
                                <Square className="h-3.5 w-3.5 text-red-600" />
                              ) : (
                                <Play className="h-3.5 w-3.5 text-green-600" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            {node.status === NodeStatus.RUNNING ? '停止节点' : '启动节点'}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>

                      {/* Batch archive button - always visible */}
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
                              disabled={node.sessions.filter(s => s.status === SessionStatus.CLOSED).length === 0}
                            >
                              <Archive className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            批量归档已关闭会话
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>

                      {/* Create session button */}
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
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
                          </TooltipTrigger>
                          <TooltipContent>
                            创建新会话
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                  </div>
                </div>

                {/* Sessions under this node */}
                {node.expanded && (
                  <div className="bg-background">
                    {node.sessions.length > 0 && (
                      node.sessions.map((session, index) => {
                        const isLast = index === node.sessions.length - 1
                        const isFirst = index === 0
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
                            {/* Tree line - VSCode style */}
                            <div className={`absolute left-[17px] ${isFirst ? '-top-[10px]' : 'top-0'} ${isFirst && isLast ? 'h-[30px]' : 'bottom-0'} w-px bg-muted-foreground/30`}>
                              {isLast && !isFirst && <div className="absolute top-5 left-0 w-px h-full bg-background" />}
                            </div>
                            <div className="absolute left-[17px] top-5 w-3 h-px bg-muted-foreground/30" />

                            {sessionListMode === 'detailed' ? (
                              /* Detailed mode: Two-line layout */
                              <div className="pl-8 pr-3 py-2">
                                {/* Line 1: Session ID + Status + Menu */}
                                <div className="flex items-center gap-2 mb-1">
                                  <span
                                    className={`font-mono text-xs truncate ${
                                      isActive ? "font-semibold" : "text-muted-foreground"
                                    }`}
                                    title={session.topic || session.session_id}
                                  >
                                    {session.topic || session.session_id.slice(0, 8)}
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
                                  <span
                                    className={`font-mono text-xs truncate ${
                                      isActive ? "font-semibold" : "text-muted-foreground"
                                    }`}
                                    title={session.topic || session.session_id}
                                  >
                                    {session.topic || session.session_id.slice(0, 8)}
                                  </span>
                                  <Circle
                                    className={`h-1.5 w-1.5 shrink-0 ml-auto ${
                                      session.status === SessionStatus.ACTIVE && session.runtime_status === RuntimeStatus.IDLE
                                        ? 'fill-green-500 text-green-500'
                                        : session.status === SessionStatus.ACTIVE && session.runtime_status === RuntimeStatus.BUSY
                                        ? 'fill-orange-500 text-orange-500'
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
                  <SelectItem value={SessionMode.LONG_RUNNING}>
                    Long Running - 长期运行模式
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
            <div className="flex items-center gap-2">
              <SheetTitle className="text-sm font-medium">会话列表</SheetTitle>
              {/* Connection status indicator */}
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div>
                      <Circle className={`h-2 w-2 ${isConnected ? 'fill-green-500 text-green-500' : 'fill-red-500 text-red-500'}`} />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isConnected ? 'WebSocket 已连接' : 'WebSocket 已断开'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
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

                      {/* Node name */}
                      <span
                        className="font-medium text-sm truncate flex-1 min-w-0"
                        title={node.node_id}
                      >
                        {node.node_id}
                      </span>

                      {/* Node control buttons */}
                      <div className="flex items-center gap-1.5 shrink-0">
                        {/* Start/Stop node button */}
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  if (node.status === NodeStatus.RUNNING) {
                                    handleStopNode(node.node_id)
                                  } else {
                                    handleStartNode(node.node_id)
                                  }
                                }}
                                disabled={nodeControlLoading[node.node_id]}
                              >
                                {nodeControlLoading[node.node_id] ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : node.status === NodeStatus.RUNNING ? (
                                  <Square className="h-3.5 w-3.5 text-red-600" />
                                ) : (
                                  <Play className="h-3.5 w-3.5 text-green-600" />
                                )}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {node.status === NodeStatus.RUNNING ? '停止节点' : '启动节点'}
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>

                        {/* Batch archive button - always visible */}
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
                                disabled={node.sessions.filter(s => s.status === SessionStatus.CLOSED).length === 0}
                              >
                                <Archive className="h-3.5 w-3.5" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              批量归档已关闭会话
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>

                        {/* Create session button */}
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
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
                            </TooltipTrigger>
                            <TooltipContent>
                              创建新会话
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </div>
                    </div>
                  </div>

                  {/* Sessions under this node */}
                  {node.expanded && (
                    <div className="bg-background">
                      {node.sessions.length > 0 && (
                        node.sessions.map((session, index) => {
                          const isLast = index === node.sessions.length - 1
                          const isFirst = index === 0
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
                              {/* Tree line - VSCode style */}
                              <div className={`absolute left-[17px] ${isFirst ? '-top-[10px]' : 'top-0'} ${isFirst && isLast ? 'h-[30px]' : 'bottom-0'} w-px bg-muted-foreground/30`}>
                                {isLast && !isFirst && <div className="absolute top-5 left-0 w-px h-full bg-background" />}
                              </div>
                              <div className="absolute left-[17px] top-5 w-3 h-px bg-muted-foreground/30" />

                              {sessionListMode === 'detailed' ? (
                                /* Detailed mode: Two-line layout */
                                <div className="pl-8 pr-3 py-2">
                                  {/* Line 1: Session ID + Status + Menu */}
                                  <div className="flex items-center gap-2 mb-1">
                                    <span
                                      className={`font-mono text-xs truncate ${
                                        isActive ? "font-semibold" : "text-muted-foreground"
                                      }`}
                                      title={session.topic || session.session_id}
                                    >
                                      {session.topic || session.session_id.slice(0, 8)}
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
                                    <span
                                      className={`font-mono text-xs truncate ${
                                        isActive ? "font-semibold" : "text-muted-foreground"
                                      }`}
                                      title={session.topic || session.session_id}
                                    >
                                      {session.topic || session.session_id.slice(0, 8)}
                                    </span>
                                    <Circle
                                      className={`h-1.5 w-1.5 shrink-0 ml-auto ${
                                        session.status === SessionStatus.ACTIVE && session.runtime_status === RuntimeStatus.IDLE
                                          ? 'fill-green-500 text-green-500'
                                          : session.status === SessionStatus.ACTIVE && session.runtime_status === RuntimeStatus.BUSY
                                          ? 'fill-orange-500 text-orange-500'
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
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
