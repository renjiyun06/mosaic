"use client"

/**
 * Sessions Chat Page - Claude Code session interaction (Full-screen mode)
 *
 * Features:
 * - Full-screen chat interface (no sidebar)
 * - Node-based session organization
 * - Real-time WebSocket chat
 * - Message history loading
 * - Session creation per node
 */

import { useState, useEffect, useRef, useCallback } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Send, Loader2, StopCircle, Plus, MessageSquare, ChevronDown, ChevronRight, Bot, Archive, Lock, ChevronLeft, ChevronRight as ChevronRightIcon } from "lucide-react"
import { useAuthStore } from "@/lib/store"
import { apiClient, API_BASE_URL, SessionResponse, MessageResponse, NodeResponse } from "@/lib/api"
import { WorkspaceExplorer } from "@/components/WorkspaceExplorer"
import { SessionMode, ClaudeModel, getSessionModeDescription, getClaudeModelFullLabel, getAvailableClaudeModels } from "@/lib/enums"
import { useWebSocket } from "@/components/websocket-provider"

interface ParsedMessage extends MessageResponse {
  contentParsed: any
}

interface NodeWithSessions extends NodeResponse {
  sessions: SessionResponse[]
  expanded: boolean
}

export default function SessionsChatPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const mosaicId = parseInt(params.mosaicId as string)
  const { token } = useAuthStore()
  const { isConnected, sendMessage, interruptSession, subscribe } = useWebSocket()

  // Get session ID from URL parameter
  const urlSessionId = searchParams.get("session")

  // Node and session management
  const [nodes, setNodes] = useState<NodeWithSessions[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ParsedMessage[]>([])

  // Input and loading states
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Session usage statistics
  const [sessionStats, setSessionStats] = useState<{
    total_cost_usd?: number
    total_input_tokens?: number
    total_output_tokens?: number
  } | null>(null)

  // Collapsed thinking messages (by message_id)
  const [collapsedThinking, setCollapsedThinking] = useState<Set<string>>(new Set())

  // Workspace explorer state
  const [workspaceWidth, setWorkspaceWidth] = useState(400) // Default 400px
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false)

  // Create session dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)
  const [sessionMode, setSessionMode] = useState<SessionMode>(SessionMode.CHAT)
  const [sessionModel, setSessionModel] = useState<ClaudeModel>(ClaudeModel.SONNET)

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const workspacePanelRef = useRef<HTMLDivElement>(null)

  // Drag state ref (pure ref, no state to avoid re-renders during drag)
  const dragStateRef = useRef({
    isDragging: false,
    startX: 0,
    startWidth: 0,
  })

  // Constants
  const WORKSPACE_MIN_WIDTH = 40 // Collapsed width
  const WORKSPACE_DEFAULT_WIDTH = 400
  const WORKSPACE_MAX_WIDTH = 800
  const COLLAPSE_THRESHOLD = 100 // Auto-collapse when dragged below this width

  // Load workspace width from localStorage
  useEffect(() => {
    const savedWidth = localStorage.getItem('workspace-width')
    const savedCollapsed = localStorage.getItem('workspace-collapsed')

    if (savedWidth) {
      const width = parseInt(savedWidth, 10)
      if (width >= WORKSPACE_MIN_WIDTH && width <= WORKSPACE_MAX_WIDTH) {
        setWorkspaceWidth(width)
      }
    }

    if (savedCollapsed === 'true') {
      setWorkspaceCollapsed(true)
    }
  }, [])

  // Load nodes and sessions on mount
  useEffect(() => {
    if (token) {
      loadNodesAndSessions()
    }
  }, [mosaicId, token])

  // Subscribe to WebSocket messages for active session
  useEffect(() => {
    if (!activeSessionId) return

    // Load message history
    loadMessages(activeSessionId)

    // Reset session stats and collapsed thinking when switching sessions
    setSessionStats(null)
    setCollapsedThinking(new Set())

    // Subscribe to messages for this session
    const unsubscribe = subscribe(activeSessionId, (message) => {
      console.log('[Chat] Received message:', message)

      if (message.type === "error") {
        console.error("[Chat] WebSocket error:", message.message)
        return
      }

      // Update session statistics if this is a result message
      if (message.type === "assistant_result" && message.content) {
        setSessionStats({
          total_cost_usd: message.content.total_cost_usd,
          total_input_tokens: message.content.total_input_tokens,
          total_output_tokens: message.content.total_output_tokens
        })
      }

      // Add message to list
      const newMessage: ParsedMessage = {
        id: 0, // Will be replaced by server
        message_id: message.message_id,
        session_id: activeSessionId,
        role: message.role,
        type: message.type,
        content: JSON.stringify(message.content),
        contentParsed: message.content,
        sequence: message.sequence,
        created_at: message.timestamp
      }

      setMessages(prev => [...prev, newMessage])

      // Collapse thinking messages by default
      if (message.type === "assistant_thinking") {
        setCollapsedThinking(prev => new Set(prev).add(message.message_id))
      }

      // Stop loading on result
      if (message.type === "assistant_result") {
        setLoading(false)
      }
    })

    // Cleanup subscription on unmount or session change
    return () => {
      unsubscribe()
    }
  }, [activeSessionId, subscribe])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const loadNodesAndSessions = async () => {
    try {
      // Load all nodes
      const nodesData = await apiClient.listNodes(mosaicId, token!)
      // Filter only Claude Code nodes
      const ccNodes = nodesData.filter(n => n.node_type === "cc")

      // Load all sessions
      const { sessions: sessionsData } = await apiClient.listSessions(token!, mosaicId)

      // Group sessions by node_id
      const nodesWithSessions: NodeWithSessions[] = ccNodes.map(node => ({
        ...node,
        sessions: sessionsData.filter(s => s.node_id === node.id),
        expanded: true // Default expanded
      }))

      setNodes(nodesWithSessions)

      // Auto-select session from URL parameter, or first active session
      if (!activeSessionId) {
        if (urlSessionId && sessionsData.find(s => s.session_id === urlSessionId)) {
          setActiveSessionId(urlSessionId)
        } else {
          // Prefer active sessions
          const activeSession = sessionsData.find(s => s.status === "active")
          if (activeSession) {
            setActiveSessionId(activeSession.session_id)
          } else if (sessionsData.length > 0) {
            // If no active session, select first one (to view history)
            setActiveSessionId(sessionsData[0].session_id)
          }
        }
      }
    } catch (error) {
      console.error("Failed to load nodes and sessions:", error)
    }
  }

  const loadMessages = async (sessionId: string) => {
    try {
      const data = await apiClient.getSessionMessages(sessionId, token!)
      const parsed = data.map(msg => ({
        ...msg,
        contentParsed: JSON.parse(msg.content)
      }))
      setMessages(parsed)

      // Collapse all thinking messages by default
      const thinkingIds = parsed
        .filter(msg => msg.type === "assistant_thinking")
        .map(msg => msg.message_id)
      setCollapsedThinking(new Set(thinkingIds))

      // Extract session stats from the last assistant_result message
      const lastResult = [...parsed].reverse().find(msg => msg.type === "assistant_result")
      if (lastResult && lastResult.contentParsed) {
        setSessionStats({
          total_cost_usd: lastResult.contentParsed.total_cost_usd,
          total_input_tokens: lastResult.contentParsed.total_input_tokens,
          total_output_tokens: lastResult.contentParsed.total_output_tokens
        })
      }
    } catch (error) {
      console.error("Failed to load messages:", error)
    }
  }

  const handleSendMessage = () => {
    if (!input.trim() || !activeSessionId || !isConnected || loading) return

    try {
      // Send message via global WebSocket
      sendMessage(activeSessionId, input)
      setInput("")
      setLoading(true)
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto"
      }
    } catch (error) {
      console.error("Failed to send message:", error)
      setLoading(false)
    }
  }

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = "auto"

    // Calculate new height (min 2 lines, max 12 lines)
    const lineHeight = 24 // approximate line height
    const minHeight = lineHeight * 1 // 1 line for input
    const maxHeight = lineHeight * 12 // max 12 lines before scroll

    const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${newHeight}px`
  }, [input])

  const handleInterrupt = () => {
    if (!activeSessionId || !isConnected || !loading) return

    try {
      // Send interrupt via global WebSocket
      interruptSession(activeSessionId)
      setLoading(false)
    } catch (error) {
      console.error("Failed to interrupt session:", error)
    }
  }

  const openCreateDialog = (nodeId: number) => {
    setSelectedNodeId(nodeId)
    setSessionMode(SessionMode.CHAT)
    setSessionModel(ClaudeModel.SONNET)
    setCreateDialogOpen(true)
  }

  const handleCreateSession = async () => {
    if (!selectedNodeId) return

    try {
      const newSession = await apiClient.createSession({
        mosaic_id: mosaicId,
        node_id: selectedNodeId,
        mode: sessionMode,
        model: sessionModel
      }, token!)

      // Update nodes with new session
      setNodes(prev => prev.map(node => {
        if (node.id === selectedNodeId) {
          return {
            ...node,
            sessions: [newSession, ...node.sessions]
          }
        }
        return node
      }))

      setActiveSessionId(newSession.session_id)
      setCreateDialogOpen(false)
    } catch (error) {
      console.error("Failed to create session:", error)
      alert("Failed to create session")
    }
  }

  const toggleNode = (nodeId: number) => {
    setNodes(prev => prev.map(node => {
      if (node.id === nodeId) {
        return { ...node, expanded: !node.expanded }
      }
      return node
    }))
  }

  const handleArchiveSession = async (sessionId: string) => {
    if (!confirm("确定要归档这个会话吗？归档后可以在历史记录中查看。")) {
      return
    }

    try {
      await apiClient.archiveSession(sessionId, token!)

      // Remove from current list
      setNodes(prev => prev.map(node => ({
        ...node,
        sessions: node.sessions.filter(s => s.session_id !== sessionId)
      })))

      // If it was active, clear selection
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
      }
    } catch (error) {
      console.error("Failed to archive session:", error)
      alert("归档失败")
    }
  }

  const handleCloseSession = async (sessionId: string) => {
    if (!confirm("确定要关闭这个会话吗？关闭后无法再发送消息，且无法重新开启。")) {
      return
    }

    try {
      const updatedSession = await apiClient.closeSession(sessionId, token!)

      // Update session status in local state
      setNodes(prev => prev.map(node => ({
        ...node,
        sessions: node.sessions.map(s =>
          s.session_id === sessionId
            ? { ...s, status: updatedSession.status }
            : s
        )
      })))
    } catch (error) {
      console.error("Failed to close session:", error)
      alert("关闭失败")
    }
  }

  // Workspace resize handlers - attach/detach listeners directly to avoid React re-render issues
  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()

    if (!workspacePanelRef.current) return

    // Store initial state
    dragStateRef.current = {
      isDragging: true,
      startX: e.clientX,
      startWidth: workspaceWidth,
    }

    // Disable transition during drag for immediate response
    workspacePanelRef.current.style.transition = 'none'

    // Set cursor immediately
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    // Define handlers as closures
    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!workspacePanelRef.current) return

      const deltaX = dragStateRef.current.startX - moveEvent.clientX
      const newWidth = Math.max(
        WORKSPACE_MIN_WIDTH,
        Math.min(WORKSPACE_MAX_WIDTH, dragStateRef.current.startWidth + deltaX)
      )

      // Update DOM directly without triggering React
      workspacePanelRef.current.style.width = `${newWidth}px`
    }

    const handleMouseUp = () => {
      if (!workspacePanelRef.current) return

      // Re-enable transition
      workspacePanelRef.current.style.transition = 'width 300ms ease-in-out'

      // Cleanup
      dragStateRef.current.isDragging = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''

      // Remove listeners
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)

      // Get final width and update state
      const finalWidth = parseInt(workspacePanelRef.current.style.width, 10)
      const shouldCollapse = finalWidth < COLLAPSE_THRESHOLD

      setWorkspaceWidth(shouldCollapse ? WORKSPACE_MIN_WIDTH : finalWidth)
      setWorkspaceCollapsed(shouldCollapse)

      // Save to localStorage
      localStorage.setItem('workspace-width', (shouldCollapse ? WORKSPACE_MIN_WIDTH : finalWidth).toString())
      localStorage.setItem('workspace-collapsed', shouldCollapse.toString())
    }

    // Attach listeners immediately
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  const toggleWorkspace = () => {
    const newCollapsed = !workspaceCollapsed
    setWorkspaceCollapsed(newCollapsed)

    if (!newCollapsed && workspaceWidth < COLLAPSE_THRESHOLD) {
      // When expanding from collapsed state, restore to default width
      setWorkspaceWidth(WORKSPACE_DEFAULT_WIDTH)
      localStorage.setItem('workspace-width', WORKSPACE_DEFAULT_WIDTH.toString())
    }

    localStorage.setItem('workspace-collapsed', newCollapsed.toString())
  }

  // Set initial transition and cleanup on unmount
  useEffect(() => {
    if (workspacePanelRef.current) {
      workspacePanelRef.current.style.transition = 'width 300ms ease-in-out'
    }

    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [])


  // Get current session and node status
  const getCurrentSession = () => {
    if (!activeSessionId) return null
    for (const node of nodes) {
      const session = node.sessions.find(s => s.session_id === activeSessionId)
      if (session) {
        return { session, nodeStatus: node.status, nodeId: node.id }
      }
    }
    return null
  }

  const currentSessionInfo = getCurrentSession()
  const canSendMessage = currentSessionInfo &&
    currentSessionInfo.nodeStatus === "running" &&
    currentSessionInfo.session.status === "active"

  const toggleThinkingCollapse = (messageId: string) => {
    setCollapsedThinking(prev => {
      const newSet = new Set(prev)
      if (newSet.has(messageId)) {
        newSet.delete(messageId)
      } else {
        newSet.add(messageId)
      }
      return newSet
    })
  }

  const renderMessage = (msg: ParsedMessage) => {
    // Don't render assistant_result messages (stats shown in header)
    if (msg.type === "assistant_result") {
      return null
    }

    const isUser = msg.role === "user"
    const isThinking = msg.type === "assistant_thinking"
    const isCollapsed = isThinking && collapsedThinking.has(msg.message_id)

    return (
      <div key={msg.message_id} className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
        <div className={`max-w-[70%] rounded-lg ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        } ${isThinking ? "px-2 py-1" : "px-4 py-2"}`}>
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
          ) : (
            <>
              {msg.type === "assistant_tool_use" && (
                <div className="text-xs opacity-70 mb-1">
                  🔧 {msg.contentParsed.tool_name}
                </div>
              )}
              <div className="text-sm whitespace-pre-wrap break-words">
                {msg.contentParsed.message || JSON.stringify(msg.contentParsed.tool_input, null, 2)}
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  // Calculate actual workspace width based on collapsed state
  const actualWorkspaceWidth = workspaceCollapsed ? WORKSPACE_MIN_WIDTH : workspaceWidth

  return (
    <div className="fixed top-14 left-0 right-0 bottom-0 bg-background">
      <div className="flex h-full">
        {/* Left Sidebar: Node tree with sessions */}
        <div className="w-80 border-r flex flex-col">
          <ScrollArea className="flex-1">
            {nodes.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>暂无 Claude Code 节点</p>
                <p className="text-xs mt-1">请先创建节点</p>
              </div>
            ) : (
              nodes.map(node => (
                <div key={node.id} className="border-b">
                  {/* Node header */}
                  <div className="p-3 bg-muted/50">
                    <div className="flex items-center gap-2 mb-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => toggleNode(node.id)}
                      >
                        {node.expanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </Button>
                      <Bot className="h-4 w-4" />
                      <span className="font-medium text-sm">{node.node_id}</span>
                      <Badge variant="outline" className="ml-auto text-xs">
                        {node.sessions.length} 会话
                      </Badge>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full h-7"
                      onClick={() => openCreateDialog(node.id)}
                      disabled={node.status !== "running"}
                    >
                      <Plus className="h-3 w-3 mr-1" />
                      新建会话
                    </Button>
                    {node.status !== "running" && (
                      <div className="mt-1 text-xs text-muted-foreground text-center">
                        节点未运行，请先启动节点
                      </div>
                    )}
                  </div>

                  {/* Sessions under this node */}
                  {node.expanded && (
                    <div>
                      {node.sessions.length === 0 ? (
                        <div className="p-3 text-center text-xs text-muted-foreground">
                          暂无会话
                        </div>
                      ) : (
                        node.sessions.map(session => (
                          <div
                            key={session.session_id}
                            className={`p-3 pl-10 hover:bg-accent border-b relative group ${
                              activeSessionId === session.session_id ? "bg-accent" : ""
                            }`}
                          >
                            <div
                              className={`cursor-pointer ${
                                session.status !== "active" ? "opacity-60" : ""
                              }`}
                              onClick={() => {
                                setActiveSessionId(session.session_id)
                                // Log info for non-active sessions
                                if (session.status !== "active") {
                                  console.log(
                                    `会话 ${session.session_id} 状态为 ${session.status}，只能查看历史消息`
                                  )
                                }
                              }}
                            >
                              <div className="flex items-center gap-2 mb-1">
                                <MessageSquare className="h-3 w-3" />
                                <span className="font-medium truncate text-xs">
                                  {session.session_id.slice(0, 8)}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{session.message_count} 消息</span>
                                {session.status === "active" && (
                                  <Badge variant="default" className="text-xs h-4 px-1">
                                    进行中
                                  </Badge>
                                )}
                                {session.status === "closed" && (
                                  <Badge variant="secondary" className="text-xs h-4 px-1">
                                    已关闭
                                  </Badge>
                                )}
                                {session.status === "archived" && (
                                  <Badge variant="outline" className="text-xs h-4 px-1">
                                    已归档
                                  </Badge>
                                )}
                              </div>
                            </div>

                            {/* Action button (centered, single button per status) */}
                            <div className="absolute right-2 top-1/2 -translate-y-1/2">
                              {/* Close button (only for active sessions) */}
                              {session.status === "active" && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleCloseSession(session.session_id)
                                  }}
                                  title="关闭会话"
                                >
                                  <Lock className="h-3 w-3" />
                                </Button>
                              )}

                              {/* Archive button (only for closed sessions) */}
                              {session.status === "closed" && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleArchiveSession(session.session_id)
                                  }}
                                  title="归档会话"
                                >
                                  <Archive className="h-3 w-3" />
                                </Button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </ScrollArea>
        </div>

        {/* Center: Chat area */}
        <div className="flex-1 flex flex-col bg-muted/20 min-w-0">
          {activeSessionId ? (
            <>
              {!isConnected ? (
                <div className="flex-1 flex items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin" />
                  <span className="ml-2">连接中...</span>
                </div>
              ) : (
                <>
                  {/* Session Info Header */}
                  <div className="border-b bg-background px-6 flex items-center justify-between shrink-0 h-11">
                    {/* Left: Session path */}
                    <div className="flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-mono text-muted-foreground">
                        {currentSessionInfo && (
                          <>
                            {nodes.find(n => n.id === currentSessionInfo.nodeId)?.node_id}
                            <span className="mx-1">/</span>
                            {activeSessionId.slice(0, 8)}
                          </>
                        )}
                      </span>
                      {currentSessionInfo && (
                        <>
                          <Badge variant="outline" className="text-xs">
                            {currentSessionInfo.session.mode || "chat"}
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            {currentSessionInfo.session.model || "sonnet"}
                          </Badge>
                        </>
                      )}
                    </div>

                    {/* Right: Usage statistics */}
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

                  <ScrollArea className="flex-1 p-6">
                    {messages.length === 0 ? (
                      <div className="flex items-center justify-center h-full text-muted-foreground">
                        <div className="text-center">
                          <MessageSquare className="h-16 w-16 mx-auto mb-4 opacity-30" />
                          <p>发送消息开始对话</p>
                        </div>
                      </div>
                    ) : (
                      <>
                        {messages.map(renderMessage)}
                        <div ref={messagesEndRef} />
                      </>
                    )}
                  </ScrollArea>

                  <div className="p-4 border-t bg-background">
                    <div className="border rounded-md bg-background overflow-hidden">
                      <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && e.ctrlKey) {
                            e.preventDefault()
                            handleSendMessage()
                          }
                        }}
                        placeholder={
                          !currentSessionInfo
                            ? "请选择会话"
                            : currentSessionInfo.session.status === "closed"
                            ? "会话已关闭，只能查看内容"
                            : currentSessionInfo.nodeStatus !== "running"
                            ? "节点未运行，无法发送消息"
                            : !isConnected
                            ? "WebSocket 连接中..."
                            : "输入消息... (Ctrl+Enter发送)"
                        }
                        disabled={loading || !isConnected || !canSendMessage}
                        className="w-full resize-none overflow-y-auto border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-3 pt-3"
                        style={{ minHeight: "24px" }}
                      />
                      <div className="flex justify-end px-2 pb-2">
                        {loading ? (
                          <Button onClick={handleInterrupt} variant="destructive" size="icon">
                            <StopCircle className="h-4 w-4" />
                          </Button>
                        ) : (
                          <Button
                            onClick={handleSendMessage}
                            disabled={!input.trim() || !isConnected || !canSendMessage}
                            size="icon"
                          >
                            <Send className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-16 w-16 mx-auto mb-4 opacity-30" />
                <p className="text-lg mb-2">选择一个会话开始对话</p>
                <p className="text-sm">或在节点下创建新会话</p>
              </div>
            </div>
          )}
        </div>
        {/* Resizable Divider with Toggle Button */}
        <div className="relative flex items-center justify-center">
          <div
            className="w-px h-full bg-border hover:bg-muted-foreground/30 active:bg-muted-foreground/50 cursor-col-resize transition-colors"
            onMouseDown={handleDragStart}
            style={{ userSelect: 'none' }}
          >
            {/* Visual feedback for dragging */}
            <div className="absolute inset-y-0 -left-1 -right-1" />
          </div>

          {/* Toggle Button - positioned in the middle of the divider */}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleWorkspace}
            className="absolute top-1/2 -translate-y-1/2 h-8 w-5 p-0 bg-background border border-border hover:bg-accent z-10"
            title={workspaceCollapsed ? "展开工作目录" : "折叠工作目录"}
          >
            {workspaceCollapsed ? (
              <ChevronLeft className="h-3 w-3" />
            ) : (
              <ChevronRightIcon className="h-3 w-3" />
            )}
          </Button>
        </div>

        {/* Right: Workspace Explorer */}
        <div
          ref={workspacePanelRef}
          className="flex flex-col bg-background overflow-hidden"
          style={{ width: `${actualWorkspaceWidth}px` }}
        >
          {workspaceCollapsed ? (
            /* Collapsed state: Show vertical label */
            <div className="flex flex-col items-center h-full justify-center">
              <div
                className="text-xs text-muted-foreground"
                style={{ writingMode: 'vertical-lr' }}
              >
                工作目录
              </div>
            </div>
          ) : currentSessionInfo?.nodeId ? (
            /* Expanded state: Show workspace content directly */
            <WorkspaceExplorer nodeId={currentSessionInfo.nodeId} />
          ) : (
            /* No session selected */
            <div className="p-4 text-center text-sm text-muted-foreground h-full flex items-center justify-center">
              <p>请选择一个会话</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Session Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>创建新会话</DialogTitle>
            <DialogDescription>
              为节点创建新的对话会话，选择会话模式和 Claude 模型
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Session Mode Selection */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">会话模式</Label>
              <RadioGroup
                value={sessionMode}
                onValueChange={(value) => setSessionMode(value as SessionMode)}
              >
                <div className="flex items-start space-x-3 space-y-0">
                  <RadioGroupItem value={SessionMode.PROGRAM} id="program" />
                  <div className="flex-1">
                    <Label
                      htmlFor="program"
                      className="font-normal cursor-pointer"
                    >
                      <div className="font-medium">程序模式</div>
                      <div className="text-sm text-muted-foreground">
                        {getSessionModeDescription(SessionMode.PROGRAM)}
                      </div>
                    </Label>
                  </div>
                </div>
                <div className="flex items-start space-x-3 space-y-0">
                  <RadioGroupItem value={SessionMode.CHAT} id="chat" />
                  <div className="flex-1">
                    <Label
                      htmlFor="chat"
                      className="font-normal cursor-pointer"
                    >
                      <div className="font-medium">对话模式</div>
                      <div className="text-sm text-muted-foreground">
                        {getSessionModeDescription(SessionMode.CHAT)}
                      </div>
                    </Label>
                  </div>
                </div>
              </RadioGroup>
            </div>

            {/* Claude Model Selection */}
            <div className="space-y-3">
              <Label htmlFor="model" className="text-sm font-medium">
                Claude 模型
              </Label>
              <Select
                value={sessionModel}
                onValueChange={(value) => setSessionModel(value as ClaudeModel)}
              >
                <SelectTrigger id="model">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {getAvailableClaudeModels().map((model) => (
                    <SelectItem key={model} value={model}>
                      {getClaudeModelFullLabel(model)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
            >
              取消
            </Button>
            <Button onClick={handleCreateSession}>创建会话</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
