import { useState, useEffect, useRef, useCallback } from "react"
import { MessageList } from "./MessageList"
import { ChatInput } from "./ChatInput"
import { type ParsedMessage } from "./MessageItem"
import { apiClient } from "@/lib/api"
import { useWebSocket } from "@/contexts/websocket-context"
import {
  SessionStatus,
  NodeStatus,
  RuntimeStatus,
  MessageRole,
  MessageType,
  type NodeOut,
  type SessionOut,
} from "@/lib/types"

interface ChatSessionProps {
  sessionId: string
  isVisible: boolean
  mosaicId: number
  nodes: Array<NodeOut & { sessions: SessionOut[] }>
  onInputChange: (sessionId: string, value: string) => void
  sessionInput: string
  onStatsUpdate?: (sessionId: string, stats: {
    total_cost_usd?: number
    total_input_tokens?: number
    total_output_tokens?: number
    context_usage?: number
    context_percentage?: number
  } | null) => void
  onScrollStateChange?: (state: { scrollTop: number; autoScrollEnabled: boolean }) => void
  initialScrollState?: { scrollTop: number; autoScrollEnabled: boolean }
}

export function ChatSession({
  sessionId,
  isVisible,
  mosaicId,
  nodes,
  onInputChange,
  sessionInput,
  onStatsUpdate,
  onScrollStateChange,
  initialScrollState,
}: ChatSessionProps) {
  const { isConnected, sendMessage, interrupt, subscribe } = useWebSocket()

  // Session-specific state
  const [messages, setMessages] = useState<ParsedMessage[]>([])
  const [collapsedMessages, setCollapsedMessages] = useState<Set<string>>(new Set())
  const [sessionStats, setSessionStats] = useState<{
    total_cost_usd?: number
    total_input_tokens?: number
    total_output_tokens?: number
    context_usage?: number
    context_percentage?: number
  } | null>(null)

  // Refs
  const maxSequenceRef = useRef<number>(0)
  const hasLoadedRef = useRef(false)

  // Find current session info
  const currentSessionInfo = nodes
    .flatMap((node) =>
      node.sessions.map((session) => ({
        nodeId: node.node_id,
        nodeStatus: node.status,
        session,
      }))
    )
    .find((info) => info.session.session_id === sessionId)

  const canSendMessage =
    currentSessionInfo?.session.status === SessionStatus.ACTIVE &&
    currentSessionInfo?.nodeStatus === NodeStatus.RUNNING

  // Load messages when nodes are ready
  useEffect(() => {
    // Wait until nodes are loaded
    if (nodes.length === 0) {
      return
    }

    // Only load once
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true

    loadMessages()
  }, [nodes])

  // WebSocket subscription
  useEffect(() => {
    const unsubscribe = subscribe(sessionId, (message) => {
      console.log("[ChatSession] Received message:", message)

      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        console.error("[ChatSession] WebSocket error:", message.message)
        return
      }

      // Type assertion: we've checked it's not an error, so it must be WSMessage
      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Verify session_id matches
      if (wsMessage.session_id !== sessionId) {
        console.warn("[ChatSession] Ignoring message from different session:", wsMessage.session_id)
        return
      }

      // Check for sequence gap (message loss detection)
      if (maxSequenceRef.current > 0) {
        const expectedSequence = maxSequenceRef.current + 1
        if (wsMessage.sequence > expectedSequence) {
          console.warn(
            `[ChatSession] Sequence gap detected! Expected ${expectedSequence}, got ${wsMessage.sequence}. Reloading messages...`
          )
          loadMessages()
          return
        }
      }

      // Update max sequence number
      maxSequenceRef.current = Math.max(maxSequenceRef.current, wsMessage.sequence)

      // Skip terminal messages (handled by WorkspaceView)
      if (wsMessage.message_type === 'terminal_output' || wsMessage.message_type === 'terminal_status') {
        return
      }

      // Skip notification messages
      if (wsMessage.role === 'notification') {
        console.log("[ChatSession] Skipping notification message:", wsMessage)
        return
      }

      // Update session statistics if this is a result message
      if (wsMessage.message_type === "assistant_result" && wsMessage.payload) {
        const stats = {
          total_cost_usd: wsMessage.payload.total_cost_usd,
          total_input_tokens: wsMessage.payload.total_input_tokens,
          total_output_tokens: wsMessage.payload.total_output_tokens,
          context_usage: wsMessage.payload.context_usage,
          context_percentage: wsMessage.payload.context_percentage,
        }
        setSessionStats(stats)
        onStatsUpdate?.(sessionId, stats)
      }

      // All non-notification messages should have message_id
      if (!wsMessage.message_id) {
        console.error("[ChatSession] Non-notification message missing message_id:", wsMessage)
        return
      }

      // Add message to list
      const newMessage: ParsedMessage = {
        id: 0,
        message_id: wsMessage.message_id,
        user_id: 0,
        mosaic_id: mosaicId,
        node_id: "",
        session_id: sessionId,
        role: wsMessage.role as MessageRole,
        message_type: wsMessage.message_type as MessageType,
        payload: wsMessage.payload,
        contentParsed: wsMessage.payload,
        sequence: wsMessage.sequence,
        created_at: wsMessage.timestamp,
      }

      // Add message with deduplication check
      setMessages((prev) => {
        // Check if message already exists (prevent duplicates in race conditions)
        if (prev.some(msg => msg.message_id === wsMessage.message_id)) {
          console.log("[ChatSession] Duplicate message detected, skipping:", wsMessage.message_id)
          return prev
        }
        return [...prev, newMessage]
      })

      // Collapse thinking, system, tool, and pre_compact messages by default
      if (
        wsMessage.message_type === "assistant_thinking" ||
        wsMessage.message_type === "system_message" ||
        wsMessage.message_type === "assistant_tool_use" ||
        wsMessage.message_type === "assistant_tool_output" ||
        wsMessage.message_type === "assistant_pre_compact"
      ) {
        setCollapsedMessages((prev) => new Set(prev).add(wsMessage.message_id!))
      }
    })

    return () => {
      unsubscribe()
    }
  }, [sessionId, subscribe])

  // Load messages from database
  const loadMessages = async () => {
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
        console.warn("[ChatSession] Node not found for session:", sessionId, "- session may be archived or deleted")
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

      setMessages(parsed)

      // Update max sequence number from loaded messages
      if (parsed.length > 0) {
        const maxSeq = Math.max(...parsed.map((msg) => msg.sequence))
        maxSequenceRef.current = maxSeq
        console.log("[ChatSession] Loaded messages, max sequence:", maxSeq)
      } else {
        maxSequenceRef.current = 0
      }

      // Collapse all thinking, system, tool, and pre_compact messages by default
      const collapsibleIds = parsed
        .filter((msg) =>
          msg.message_type === MessageType.ASSISTANT_THINKING ||
          msg.message_type === MessageType.SYSTEM_MESSAGE ||
          msg.message_type === MessageType.ASSISTANT_TOOL_USE ||
          msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT ||
          msg.message_type === MessageType.ASSISTANT_PRE_COMPACT
        )
        .map((msg) => msg.message_id)
      setCollapsedMessages(new Set(collapsibleIds))

      // Extract session stats from the last assistant_result message
      const lastResult = [...parsed].reverse().find((msg) => msg.message_type === MessageType.ASSISTANT_RESULT)
      if (lastResult && lastResult.contentParsed) {
        const stats = {
          total_cost_usd: lastResult.contentParsed.total_cost_usd,
          total_input_tokens: lastResult.contentParsed.total_input_tokens,
          total_output_tokens: lastResult.contentParsed.total_output_tokens,
          context_usage: lastResult.contentParsed.context_usage,
          context_percentage: lastResult.contentParsed.context_percentage,
        }
        setSessionStats(stats)
        onStatsUpdate?.(sessionId, stats)
      }
    } catch (error) {
      console.error("Failed to load messages:", error)
    }
  }

  // Handle send message
  const handleSendMessage = useCallback((sessionId: string, message: string) => {
    sendMessage(sessionId, message)
    onInputChange(sessionId, "")
  }, [sendMessage, onInputChange])

  // Handle interrupt
  const handleInterrupt = useCallback((sessionId: string) => {
    interrupt(sessionId)
  }, [interrupt])

  // Toggle collapsed state
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

  return (
    <div
      className="flex flex-col flex-1 min-h-0"
      style={{
        display: isVisible ? 'flex' : 'none',
      }}
    >
      {/* Messages Area */}
      <MessageList
        messages={messages}
        collapsedMessages={collapsedMessages}
        isLoading={currentSessionInfo?.session.runtime_status === RuntimeStatus.BUSY}
        isVisible={isVisible}
        onToggleCollapse={toggleCollapse}
        sessionId={sessionId}
        onScrollStateChange={onScrollStateChange}
        initialScrollState={initialScrollState}
      />

      {/* Input Area */}
      <ChatInput
        sessionId={sessionId}
        initialValue={sessionInput}
        isBusy={currentSessionInfo?.session.runtime_status === RuntimeStatus.BUSY}
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
        onInputChange={onInputChange}
      />
    </div>
  )
}

export type { ParsedMessage }
