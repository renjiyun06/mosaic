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

import { useState, useEffect, useRef, useCallback } from "react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
} from "@/lib/types"

interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface NodeWithSessions extends NodeOut {
  sessions: SessionOut[]
  expanded: boolean
}

export default function ChatPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = parseInt(params.mosaicId as string)
  const { isConnected, sendMessage, interrupt, subscribe } = useWebSocket()

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

  // Create session dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [sessionMode, setSessionMode] = useState<SessionMode>(SessionMode.CHAT)
  const [sessionModel, setSessionModel] = useState<LLMModel>(LLMModel.SONNET)
  const [creating, setCreating] = useState(false)

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load nodes and sessions on mount
  useEffect(() => {
    if (!token) return
    loadNodesAndSessions()
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
      console.log("[Chat] Received message:", message)

      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        console.error("[Chat] WebSocket error:", message.message)
        return
      }

      // Type assertion: we've checked it's not an error, so it must be WSMessage
      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Update session statistics if this is a result message
      if (wsMessage.message_type === "assistant_result" && wsMessage.payload) {
        setSessionStats({
          total_cost_usd: wsMessage.payload.total_cost_usd,
          total_input_tokens: wsMessage.payload.total_input_tokens,
          total_output_tokens: wsMessage.payload.total_output_tokens,
        })
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

      // Collapse thinking messages by default
      if (wsMessage.message_type === "assistant_thinking") {
        setCollapsedThinking((prev) => new Set(prev).add(wsMessage.message_id))
      }

      // Stop loading on result
      if (wsMessage.message_type === "assistant_result") {
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
  }

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

      const data = await apiClient.listMessages(mosaicId, nodeId, sessionId)
      const parsed = data.items.map((msg) => ({
        ...msg,
        contentParsed: typeof msg.payload === "string" ? JSON.parse(msg.payload) : msg.payload,
      }))
      setMessages(parsed)

      // Collapse all thinking messages by default
      const thinkingIds = parsed
        .filter((msg) => msg.message_type === MessageType.ASSISTANT_THINKING)
        .map((msg) => msg.message_id)
      setCollapsedThinking(new Set(thinkingIds))

      // Extract session stats from the last assistant_result message
      const lastResult = [...parsed].reverse().find((msg) => msg.message_type === MessageType.ASSISTANT_RESULT)
      if (lastResult && lastResult.contentParsed) {
        setSessionStats({
          total_cost_usd: lastResult.contentParsed.total_cost_usd,
          total_input_tokens: lastResult.contentParsed.total_input_tokens,
          total_output_tokens: lastResult.contentParsed.total_output_tokens,
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

    // Calculate new height (min 1 line, max 12 lines)
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
      interrupt(activeSessionId)
      setLoading(false)
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

      // Update nodes with new session
      setNodes((prev) =>
        prev.map((node) => {
          if (node.node_id === selectedNodeId) {
            return {
              ...node,
              sessions: [newSession, ...node.sessions],
            }
          }
          return node
        })
      )

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
    if (!confirm("确定要归档这个会话吗？归档后可以在历史记录中查看。")) {
      return
    }

    try {
      await apiClient.archiveSession(mosaicId, nodeId, sessionId)

      // Remove from current list
      setNodes((prev) =>
        prev.map((node) => ({
          ...node,
          sessions: node.sessions.filter((s) => s.session_id !== sessionId),
        }))
      )

      // If it was active, clear selection
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
      }
    } catch (error) {
      console.error("Failed to archive session:", error)
    }
  }

  const handleCloseSession = async (sessionId: string, nodeId: string) => {
    if (!confirm("确定要关闭这个会话吗？关闭后无法再发送消息，且无法重新开启。")) {
      return
    }

    try {
      const updatedSession = await apiClient.closeSession(mosaicId, nodeId, sessionId)

      // Update session status in local state
      setNodes((prev) =>
        prev.map((node) => ({
          ...node,
          sessions: node.sessions.map((s) =>
            s.session_id === sessionId ? { ...s, status: updatedSession.status } : s
          ),
        }))
      )
    } catch (error) {
      console.error("Failed to close session:", error)
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
    setCollapsedThinking((prev) => {
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
    if (msg.message_type === MessageType.ASSISTANT_RESULT) {
      return null
    }

    const isUser = msg.role === MessageRole.USER
    const isThinking = msg.message_type === MessageType.ASSISTANT_THINKING
    const isCollapsed = isThinking && collapsedThinking.has(msg.message_id)

    return (
      <div
        key={msg.message_id}
        className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
      >
        <div
          className={`max-w-[70%] rounded-lg ${
            isUser ? "bg-primary text-primary-foreground" : "bg-muted"
          } ${isThinking ? "px-2 py-1" : "px-4 py-2"}`}
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
          ) : (
            <>
              {msg.message_type === MessageType.ASSISTANT_TOOL_USE && (
                <div className="text-xs opacity-70 mb-1">
                  🔧 {msg.contentParsed.tool_name}
                </div>
              )}
              <div className="text-sm whitespace-pre-wrap break-words">
                {msg.contentParsed.message ||
                  JSON.stringify(msg.contentParsed.tool_input, null, 2)}
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex absolute inset-0 overflow-hidden">
      {/* Middle: Chat Area */}
      <div className="flex-1 flex flex-col bg-muted/20 min-w-0">
        {!activeSessionId ? (
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
            {/* Session Info Header */}
            <div className="border-b bg-background px-6 flex items-center justify-between shrink-0 h-11">
              {/* Left: Session path */}
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-mono text-muted-foreground">
                  {currentSessionInfo && (
                    <>
                      {currentSessionInfo.nodeId}
                      <span className="mx-1">/</span>
                      {activeSessionId.slice(0, 8)}
                    </>
                  )}
                </span>
                {currentSessionInfo && (
                  <>
                    <Badge variant="outline" className="text-xs">
                      {currentSessionInfo.session.mode}
                    </Badge>
                    {currentSessionInfo.session.model && (
                      <Badge variant="outline" className="text-xs">
                        {currentSessionInfo.session.model}
                      </Badge>
                    )}
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
                  {messages.map(renderMessage)}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input Area */}
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
                      : currentSessionInfo.session.status === SessionStatus.CLOSED
                      ? "会话已关闭，只能查看内容"
                      : currentSessionInfo.nodeStatus !== NodeStatus.RUNNING
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
      </div>

      {/* Right: Session List */}
      <div className="w-80 border-l flex flex-col">
        <div
          className="flex-1 overflow-y-auto"
          style={{
            scrollbarWidth: 'thin',
            scrollbarColor: 'hsl(var(--border)) transparent'
          }}
        >
          {nodes.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground border rounded-lg mx-4 mt-16">
              <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>暂无 Claude Code 节点</p>
              <p className="text-xs mt-1">请先创建节点</p>
            </div>
          ) : (
            nodes.map((node) => (
              <div key={node.node_id} className="border-b">
                {/* Node header */}
                <div className="p-3 bg-muted/50">
                  <div className="flex items-center gap-2 mb-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => toggleNode(node.node_id)}
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
                    onClick={() => openCreateDialog(node.node_id)}
                    disabled={node.status !== NodeStatus.RUNNING}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    新建会话
                  </Button>
                  {node.status !== NodeStatus.RUNNING && (
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
                      node.sessions.map((session) => (
                        <div
                          key={session.session_id}
                          className={`p-3 cursor-pointer hover:bg-muted/50 border-l-2 ${
                            activeSessionId === session.session_id
                              ? "border-l-primary bg-muted/50"
                              : "border-l-transparent"
                          }`}
                          onClick={() => setActiveSessionId(session.session_id)}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-xs text-muted-foreground">
                              {session.session_id.slice(0, 8)}
                            </span>
                            <div className="flex items-center gap-1">
                              <Badge
                                variant={
                                  session.status === SessionStatus.ACTIVE
                                    ? "default"
                                    : "secondary"
                                }
                                className="text-xs h-5"
                              >
                                {session.status === SessionStatus.ACTIVE && "活跃"}
                                {session.status === SessionStatus.CLOSED && "已关闭"}
                                {session.status === SessionStatus.ARCHIVED && "已归档"}
                              </Badge>

                              {/* Close button (only for active sessions) */}
                              {session.status === SessionStatus.ACTIVE && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleCloseSession(session.session_id, node.node_id)
                                  }}
                                  title="关闭会话"
                                >
                                  <Lock className="h-3 w-3" />
                                </Button>
                              )}

                              {/* Archive button (only for closed sessions) */}
                              {session.status === SessionStatus.CLOSED && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleArchiveSession(session.session_id, node.node_id)
                                  }}
                                  title="归档会话"
                                >
                                  <Archive className="h-3 w-3" />
                                </Button>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              {session.mode}
                            </Badge>
                            {session.model && (
                              <Badge variant="outline" className="text-xs">
                                {session.model}
                              </Badge>
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
    </div>
  )
}
