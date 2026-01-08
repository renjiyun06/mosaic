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

import { useState, useEffect, useRef, useCallback, Fragment } from "react"
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
  Search,
  List,
  LayoutList,
  FolderTree,
  Circle,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { useWebSocket } from "@/contexts/websocket-context"
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

interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface NodeWithSessions extends NodeOut {
  sessions: SessionOut[]
  expanded: boolean
}

// Workspace file tree types (extend WorkspaceFileItem with expanded state)
interface FileNode extends WorkspaceFileItem {
  expanded?: boolean
}

type ViewMode = 'chat' | 'workspace'
type SessionListMode = 'detailed' | 'compact'

export default function ChatPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = parseInt(params.mosaicId as string)
  const { isConnected, sendMessage, interrupt, subscribe } = useWebSocket()

  // View mode
  const [viewMode, setViewMode] = useState<ViewMode>('chat')

  // Session list mode and search
  const [sessionListMode, setSessionListMode] = useState<SessionListMode>('compact')
  const [searchQuery, setSearchQuery] = useState('')
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null)

  // Node and session management
  const [nodes, setNodes] = useState<NodeWithSessions[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ParsedMessage[]>([])

  // Workspace state
  const [fileTree, setFileTree] = useState<FileNode[]>([])
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string; language: string | null } | null>(null)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [fileContentLoading, setFileContentLoading] = useState(false)

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
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const maxSequenceRef = useRef<number>(0) // Track max sequence number for gap detection
  const sessionStartedResolvers = useRef<Map<string, (value: boolean) => void>>(new Map())

  // Load nodes and sessions function
  const loadNodesAndSessions = useCallback(async () => {
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

      // Auto-select first active session
      if (!activeSessionId) {
        const allSessions = nodesWithSessions.flatMap((n) => n.sessions)
        const activeSession = allSessions.find((s) => s.status === SessionStatus.ACTIVE)
        if (activeSession) {
          setActiveSessionId(activeSession.session_id)
        } else if (allSessions.length > 0) {
          // If no active session, select first one (to view history)
          setActiveSessionId(allSessions[0].session_id)
        }
      }
    } catch (error) {
      console.error("Failed to load nodes and sessions:", error)
    }
  }, [mosaicId, activeSessionId])

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

  // Subscribe to WebSocket messages for active session
  useEffect(() => {
    if (!activeSessionId) return

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

  // Auto-scroll to bottom
  useEffect(() => {
    console.log("[Chat] Messages changed, count:", messages.length)
    if (messages.length > 0) {
      console.log("[Chat] Message IDs in state:", messages.map(m => `${m.message_id.slice(0, 8)} (seq: ${m.sequence})`))
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

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

  // Load workspace when switching to workspace view or when active session changes
  useEffect(() => {
    if (viewMode === 'workspace' && currentSessionInfo) {
      loadWorkspace(currentSessionInfo.nodeId)
    }
  }, [viewMode, activeSessionId])

  const loadMessages = async (sessionId: string) => {
    try {
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

  const handleSendMessage = () => {
    const input = currentInput
    if (!input.trim() || !activeSessionId || !isConnected || currentLoading) return

    try {
      // Send message via global WebSocket
      sendMessage(activeSessionId, input)
      // Clear current session's input
      setSessionInputs(prev => ({
        ...prev,
        [activeSessionId]: ""
      }))
      // Set current session's loading state
      setSessionLoadings(prev => ({
        ...prev,
        [activeSessionId]: true
      }))
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto"
      }
    } catch (error) {
      console.error("Failed to send message:", error)
      setSessionLoadings(prev => ({
        ...prev,
        [activeSessionId]: false
      }))
    }
  }

  // Auto-resize textarea based on content
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
  }, [currentInput])

  // Auto-focus textarea when loading finishes
  useEffect(() => {
    if (!currentLoading && activeSessionId && isConnected && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [currentLoading, activeSessionId, isConnected])

  const handleInterrupt = () => {
    if (!activeSessionId || !isConnected || !currentLoading) return

    try {
      // Send interrupt via global WebSocket
      interrupt(activeSessionId)
      setSessionLoadings(prev => ({
        ...prev,
        [activeSessionId]: false
      }))
    } catch (error) {
      console.error("Failed to interrupt session:", error)
    }
  }

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
      setActiveSessionId(newSession.session_id)
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
        setActiveSessionId(null)
      }
    } catch (error) {
      console.error("Failed to archive session:", error)
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

  const toggleThinkingCollapse = (messageId: string) => {
    setCollapsedMessages((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(messageId)) {
        newSet.delete(messageId)
      } else {
        newSet.add(messageId)
      }
      return newSet
    })
  }

  // Filter sessions based on search query
  const filteredNodes = nodes.map(node => {
    if (!searchQuery.trim()) return node

    const query = searchQuery.toLowerCase()
    const filteredSessions = node.sessions.filter(session =>
      session.session_id.toLowerCase().includes(query) ||
      session.mode.toLowerCase().includes(query) ||
      (session.model && session.model.toLowerCase().includes(query))
    )

    return { ...node, sessions: filteredSessions }
  }).filter(node => {
    // Only filter out nodes with no sessions when searching
    // Always show all nodes when not searching (even if they have no sessions)
    return !searchQuery.trim() || node.sessions.length > 0
  })

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
              <span className="w-4" />
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
          <span className="text-sm truncate">{node.name}</span>
        </div>
        {node.type === 'directory' && node.expanded && node.children && (
          <div>{renderFileTree(node.children, nodeId, level + 1)}</div>
        )}
      </div>
    ))
  }

  const renderMessage = (msg: ParsedMessage) => {
    console.log("[Chat] renderMessage called for:", {
      message_id: msg.message_id,
      message_type: msg.message_type,
      role: msg.role,
      sequence: msg.sequence
    })

    // Don't render assistant_result messages (stats shown in header)
    if (msg.message_type === MessageType.ASSISTANT_RESULT) {
      console.log("[Chat] Skipping ASSISTANT_RESULT message:", msg.message_id)
      return null
    }

    const isUser = msg.role === MessageRole.USER
    const isThinking = msg.message_type === MessageType.ASSISTANT_THINKING
    const isSystemMessage = msg.message_type === MessageType.SYSTEM_MESSAGE
    const isToolUse = msg.message_type === MessageType.ASSISTANT_TOOL_USE
    const isToolOutput = msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT
    const isCollapsible = isThinking || isSystemMessage || isToolUse || isToolOutput
    const isCollapsed = isCollapsible && collapsedMessages.has(msg.message_id)

    // Debug log for tool_output messages
    if (isToolOutput) {
      console.log("[Chat] Rendering tool_output:", {
        message_id: msg.message_id,
        tool_name: msg.contentParsed?.tool_name,
        tool_output_type: typeof msg.contentParsed?.tool_output,
        tool_output_length: typeof msg.contentParsed?.tool_output === 'string'
          ? msg.contentParsed.tool_output.length
          : JSON.stringify(msg.contentParsed?.tool_output || {}).length,
        payload: msg.contentParsed
      })
    }

    return (
      <div
        className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
      >
        <div
          className={`max-w-[70%] rounded-lg ${
            isUser ? "bg-primary text-primary-foreground" : "bg-muted"
          } ${isCollapsible ? "px-2 py-1" : "px-4 py-2"}`}
        >
          {isThinking ? (
            <div>
              <div
                className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
                onClick={() => toggleThinkingCollapse(msg.message_id)}
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
                onClick={() => toggleThinkingCollapse(msg.message_id)}
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
                onClick={() => toggleThinkingCollapse(msg.message_id)}
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
                onClick={() => toggleThinkingCollapse(msg.message_id)}
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
  }

  return (
    <div className="flex absolute inset-0 overflow-hidden">
      {/* Middle: Main Content Area */}
      <div className="flex-1 flex flex-col bg-muted/20 min-w-0">
        {/* Tab Switcher + Header */}
        <div className="border-b bg-background flex items-center justify-between shrink-0 h-11">
          {/* Left: Tab buttons */}
          <div className="flex items-center">
            <Button
              variant={viewMode === 'chat' ? 'default' : 'ghost'}
              size="sm"
              className="rounded-none h-11 px-6"
              onClick={() => setViewMode('chat')}
            >
              <MessageSquare className="h-4 w-4 mr-2" />
              聊天
            </Button>
            <Button
              variant={viewMode === 'workspace' ? 'default' : 'ghost'}
              size="sm"
              className="rounded-none h-11 px-6"
              onClick={() => setViewMode('workspace')}
            >
              <Folder className="h-4 w-4 mr-2" />
              工作区
            </Button>
          </div>

          {/* Right: Session info and stats */}
          {viewMode === 'chat' && currentSessionInfo && (
            <div className="flex items-center gap-4 px-6">
              {/* Session path */}
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono text-muted-foreground">
                  {currentSessionInfo.nodeId}
                  <span className="mx-1">/</span>
                  {activeSessionId?.slice(0, 8)}
                </span>
                <Badge variant="outline" className="text-xs">
                  {currentSessionInfo.session.mode}
                </Badge>
                {currentSessionInfo.session.model && (
                  <Badge variant="outline" className="text-xs">
                    {currentSessionInfo.session.model}
                  </Badge>
                )}
              </div>

              {/* WebSocket status */}
              {currentSessionInfo.session.status === SessionStatus.ACTIVE && (
                <div className="flex items-center">
                  <div
                    className={`h-2 w-2 rounded-full ${
                      isConnected ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                </div>
              )}

              {/* Usage statistics */}
              {sessionStats && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
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
            </div>
          )}

          {/* Workspace header */}
          {viewMode === 'workspace' && (
            <div className="flex items-center gap-2 px-6">
              <span className="text-sm text-muted-foreground">
                {currentSessionInfo ? `节点: ${currentSessionInfo.nodeId}` : '请选择会话'}
              </span>
            </div>
          )}
        </div>

        {/* Content Area - Switch between Chat and Workspace */}
        {viewMode === 'chat' ? (
          /* Chat View */
          !activeSessionId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <MessageSquare className="h-16 w-16 mx-auto mb-4 opacity-30" />
                <p>请选择一个会话</p>
              </div>
            </div>
          ) : !isConnected ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin" />
              <span className="ml-2">连接中...</span>
            </div>
          ) : (
            <>
              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto p-6">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <div className="text-center">
                    <MessageSquare className="h-16 w-16 mx-auto mb-4 opacity-30" />
                    <p>发送消息开始对话</p>
                  </div>
                </div>
              ) : (
                <>
                  {(() => {
                    console.log("[Chat] Rendering messages, total count:", messages.length)
                    console.log("[Chat] Message IDs:", messages.map(m => m.message_id))

                    // Check for tool_output messages
                    const toolOutputCount = messages.filter(m => m.message_type === MessageType.ASSISTANT_TOOL_OUTPUT).length
                    if (toolOutputCount > 0) {
                      console.log(`[Chat] Found ${toolOutputCount} tool_output messages in render queue`)
                      console.log("[Chat] Tool output messages:", messages
                        .filter(m => m.message_type === MessageType.ASSISTANT_TOOL_OUTPUT)
                        .map(m => ({
                          message_id: m.message_id,
                          sequence: m.sequence,
                          message_type: m.message_type,
                          contentParsed: m.contentParsed
                        }))
                      )
                    }

                    // Check for duplicate message_ids
                    const ids = messages.map(m => m.message_id)
                    const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index)
                    if (duplicates.length > 0) {
                      console.error("[Chat] DUPLICATE message_ids found:", duplicates)
                    }

                    return messages.map((msg) => {
                      console.log("[Chat] Mapping message:", msg.message_id)
                      // Use message_id as key since it's guaranteed to exist and be unique
                      return (
                        <Fragment key={msg.message_id}>
                          {renderMessage(msg)}
                        </Fragment>
                      )
                    })
                  })()}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t bg-background">
              <div className="bg-background overflow-hidden">
                <Textarea
                  ref={textareaRef}
                  value={currentInput}
                  onChange={(e) => {
                    if (activeSessionId) {
                      setSessionInputs(prev => ({
                        ...prev,
                        [activeSessionId]: e.target.value
                      }))
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && e.ctrlKey) {
                      e.preventDefault()
                      handleSendMessage()
                    }
                  }}
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
                  disabled={currentLoading || !isConnected || !canSendMessage}
                  className="w-full resize-none overflow-y-auto border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-3 pt-3"
                  style={{ minHeight: "24px" }}
                />
                <div className="flex justify-end px-2 pb-2">
                  {currentLoading ? (
                    <Button onClick={handleInterrupt} variant="destructive" size="icon">
                      <StopCircle className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      onClick={handleSendMessage}
                      disabled={!currentInput.trim() || !isConnected || !canSendMessage}
                      size="icon"
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </>
        )
        ) : (
          /* Workspace View */
          !activeSessionId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Folder className="h-16 w-16 mx-auto mb-4 opacity-30" />
                <p>请选择一个会话查看工作区</p>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex overflow-hidden">
              {/* Left: File Tree */}
              <div className="w-80 border-r bg-background overflow-y-auto">
                <div className="px-3 py-1.5 border-b bg-background flex items-center justify-between shrink-0">
                  <div className="flex items-center gap-2">
                    <Folder className="h-4 w-4" />
                    <span className="text-sm font-medium">文件树</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    onClick={() => currentSessionInfo && loadWorkspace(currentSessionInfo.nodeId)}
                    disabled={workspaceLoading}
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${workspaceLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <div className="py-2">
                  {workspaceLoading ? (
                    <div className="p-4 text-center text-sm text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                      加载中...
                    </div>
                  ) : fileTree.length === 0 ? (
                    <div className="p-4 text-center text-sm text-muted-foreground">
                      工作区为空
                    </div>
                  ) : (
                    currentSessionInfo && renderFileTree(fileTree, currentSessionInfo.nodeId)
                  )}
                </div>
              </div>

              {/* Right: File Content Viewer */}
              <div className="flex-1 flex flex-col bg-muted/20 overflow-hidden">
                {fileContentLoading ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center text-muted-foreground">
                      <Loader2 className="h-12 w-12 animate-spin mx-auto mb-2" />
                      <p>加载文件内容...</p>
                    </div>
                  </div>
                ) : selectedFile ? (
                  <>
                    {/* File header */}
                    <div className="border-b bg-background px-4 py-2 shrink-0">
                      <div className="flex items-center gap-2">
                        <FileCode className="h-4 w-4 text-blue-500" />
                        <span className="text-sm font-mono">{selectedFile.path}</span>
                      </div>
                    </div>
                    {/* File content */}
                    <div className="flex-1 overflow-auto">
                      <pre className="p-4 text-sm font-mono">
                        <code>{selectedFile.content}</code>
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center text-muted-foreground">
                      <FileText className="h-16 w-16 mx-auto mb-4 opacity-30" />
                      <p>选择一个文件查看内容</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        )}
      </div>

      {/* Right: Session List */}
      <div className="w-80 border-l flex flex-col bg-background">
        {/* Header with mode toggle */}
        <div className="h-11 border-b px-3 flex items-center justify-between shrink-0">
          <span className="text-sm font-medium">会话</span>
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

        {/* Search bar */}
        <div className="px-3 py-2 border-b">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索会话..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-sm"
            />
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
          {filteredNodes.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              {searchQuery ? (
                <>
                  <Search className="h-12 w-12 mx-auto mb-2 opacity-30" />
                  <p>未找到匹配的会话</p>
                </>
              ) : (
                <>
                  <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>暂无 Claude Code 节点</p>
                  <p className="text-xs mt-1">请先创建节点</p>
                </>
              )}
            </div>
          ) : (
            filteredNodes.map((node) => (
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

                    {/* Session count and create button */}
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-xs text-muted-foreground">
                        {node.sessions.length}
                      </span>
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
                            onClick={() => setActiveSessionId(session.session_id)}
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
        <DialogContent className="max-h-[90vh] overflow-y-scroll">
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
        <DialogContent>
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
    </div>
  )
}
