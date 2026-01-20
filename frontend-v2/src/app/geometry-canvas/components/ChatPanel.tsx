'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { ChevronRight, MessageSquare, Plus } from 'lucide-react'
import { getGeoGebraAPI } from './GeoGebraShape'
import { NodeSelector } from './NodeSelector'
import { useWebSocket } from '@/contexts/websocket-context'
import type { WSMessage, GeoGebraInstanceState, GeoGebraObject, MessageContext } from '@/contexts/websocket-context'
import { apiClient } from '@/lib/api'
import { MessageList } from './MessageList'
import type { ParsedMessage } from './MessageItem'
import { MessageRole, MessageType, RuntimeStatus, SessionStatus, NodeStatus, SessionMode } from '@/lib/types'
import { ChatInput } from './ChatInput'

interface ChatPanelProps {
  editor: any | null
  isVisible: boolean
  onToggle: () => void
}

export function ChatPanel({ editor, isVisible, onToggle }: ChatPanelProps) {
  const { isConnected, sendMessage, interrupt, subscribe, sendRaw } = useWebSocket()

  const [messages, setMessages] = useState<ParsedMessage[]>([])
  const [collapsedMessages, setCollapsedMessages] = useState<Set<string>>(new Set())
  const [sessionInput, setSessionInput] = useState('')
  const [selectedMosaicId, setSelectedMosaicId] = useState<number | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [currentSessionStatus, setCurrentSessionStatus] = useState<SessionStatus | null>(null)
  const [currentRuntimeStatus, setCurrentRuntimeStatus] = useState<RuntimeStatus>(RuntimeStatus.IDLE)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingSession, setIsLoadingSession] = useState(false)
  const [nodeStatus, setNodeStatus] = useState<NodeStatus>(NodeStatus.RUNNING) // Assume running by default

  const hasCreatedSessionRef = useRef(false)
  const hasLoadedRef = useRef(false)
  const maxSequenceRef = useRef<number>(0)

  // Handle node selection
  const handleNodeSelect = useCallback((mosaicId: number, nodeId: string) => {
    setSelectedMosaicId(mosaicId)
    setSelectedNodeId(nodeId)
    setCurrentSessionId(null)
    setCurrentSessionStatus(null)
    setCurrentRuntimeStatus(RuntimeStatus.IDLE)
    setMessages([]) // Clear messages on node change
    setSessionInput('') // Clear input on node change
    hasCreatedSessionRef.current = false
    hasLoadedRef.current = false
    maxSequenceRef.current = 0
    console.log('[ChatPanel] Selected node:', { mosaicId, nodeId })
  }, [])

  // Load messages from database
  const loadMessages = useCallback(async () => {
    if (!selectedMosaicId || !selectedNodeId || !currentSessionId) {
      return
    }

    try {
      setIsLoading(true)
      const data = await apiClient.listMessages(selectedMosaicId, {
        nodeId: selectedNodeId,
        sessionId: currentSessionId,
        page: 1,
        pageSize: 9999,
      })

      const parsed = data.items.map((msg) => ({
        ...msg,
        contentParsed: typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload,
      }))

      setMessages(parsed)

      // Update max sequence number
      if (parsed.length > 0) {
        const maxSeq = Math.max(...parsed.map((msg) => msg.sequence))
        maxSequenceRef.current = maxSeq
        console.log('[ChatPanel] Loaded messages, max sequence:', maxSeq)
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
    } catch (error) {
      console.error('[ChatPanel] Failed to load messages:', error)
    } finally {
      setIsLoading(false)
    }
  }, [selectedMosaicId, selectedNodeId, currentSessionId])

  // Load latest session when node is selected
  useEffect(() => {
    if (!selectedMosaicId || !selectedNodeId) {
      return
    }

    // Prevent multiple loads
    if (hasCreatedSessionRef.current) {
      return
    }

    hasCreatedSessionRef.current = true
    setIsLoadingSession(true)

    // Load the latest session (by last_activity_at)
    apiClient
      .listSessions(selectedMosaicId, selectedNodeId, {
        page: 1,
        page_size: 1,
      })
      .then((response) => {
        if (response.items.length > 0) {
          const latestSession = response.items[0]
          console.log('[ChatPanel] Loaded latest session:', latestSession.session_id, 'status:', latestSession.status, 'runtime_status:', latestSession.runtime_status)
          setCurrentSessionId(latestSession.session_id)
          setCurrentSessionStatus(latestSession.status)
          setCurrentRuntimeStatus(latestSession.runtime_status || RuntimeStatus.IDLE)
        } else {
          console.log('[ChatPanel] No sessions found for node:', selectedNodeId)
          setCurrentSessionId(null)
          setCurrentSessionStatus(null)
          setCurrentRuntimeStatus(RuntimeStatus.IDLE)
        }
      })
      .catch((error) => {
        console.error('[ChatPanel] Failed to load sessions:', error)
        hasCreatedSessionRef.current = false
      })
      .finally(() => {
        setIsLoadingSession(false)
      })
  }, [selectedMosaicId, selectedNodeId])

  // Load messages when session is ready
  useEffect(() => {
    if (!currentSessionId || hasLoadedRef.current) {
      return
    }

    hasLoadedRef.current = true
    loadMessages()
  }, [currentSessionId, loadMessages])

  // Subscribe to WebSocket messages
  useEffect(() => {
    if (!currentSessionId) {
      return
    }

    console.log('[ChatPanel] Subscribing to session:', currentSessionId)

    const unsubscribe = subscribe(currentSessionId, (message) => {
      console.log('[ChatPanel] Received message:', message)

      // Check if it's an error message
      if ('type' in message && message.type === 'error') {
        console.error('[ChatPanel] WebSocket error:', message.message)
        return
      }

      // Type assertion: it's a WSMessage
      const wsMessage = message as WSMessage

      // Verify session_id matches
      if (wsMessage.session_id !== currentSessionId) {
        console.warn('[ChatPanel] Ignoring message from different session:', wsMessage.session_id)
        return
      }

      // Check for sequence gap (message loss detection)
      if (maxSequenceRef.current > 0) {
        const expectedSequence = maxSequenceRef.current + 1
        if (wsMessage.sequence > expectedSequence) {
          console.warn(
            `[ChatPanel] Sequence gap detected! Expected ${expectedSequence}, got ${wsMessage.sequence}. Reloading messages...`
          )
          loadMessages()
          return
        }
      }

      // Update max sequence number
      maxSequenceRef.current = Math.max(maxSequenceRef.current, wsMessage.sequence)

      // Handle GeoGebra command messages
      if (wsMessage.message_type === MessageType.GEOGEBRA_COMMAND) {
        console.log('[ChatPanel] Received GeoGebra command:', wsMessage.payload)
        handleGeoGebraCommand(wsMessage.payload)
        return
      }

      // Skip terminal messages
      if (wsMessage.message_type === 'terminal_output' || wsMessage.message_type === 'terminal_status') {
        return
      }

      // Handle notification messages
      if (wsMessage.role === 'notification') {
        console.log('[ChatPanel] Received notification message:', wsMessage)
        // Update runtime status when it changes
        if (wsMessage.message_type === 'runtime_status_changed' && wsMessage.payload?.runtime_status) {
          console.log('[ChatPanel] Runtime status changed to:', wsMessage.payload.runtime_status)
          setCurrentRuntimeStatus(wsMessage.payload.runtime_status)
        }
        return
      }

      // All non-notification messages should have message_id
      if (!wsMessage.message_id) {
        console.error('[ChatPanel] Non-notification message missing message_id:', wsMessage)
        return
      }

      // Add message to list
      const newMessage: ParsedMessage = {
        id: 0,
        message_id: wsMessage.message_id,
        user_id: 0,
        mosaic_id: selectedMosaicId || 0,
        node_id: selectedNodeId || '',
        session_id: currentSessionId,
        role: wsMessage.role as MessageRole,
        message_type: wsMessage.message_type as MessageType,
        payload: wsMessage.payload,
        contentParsed: wsMessage.payload,
        sequence: wsMessage.sequence,
        created_at: wsMessage.timestamp,
      }

      // Add message with deduplication check
      setMessages((prev) => {
        // Check if message already exists
        if (prev.some((msg) => msg.message_id === wsMessage.message_id)) {
          console.log('[ChatPanel] Duplicate message detected, skipping:', wsMessage.message_id)
          return prev
        }
        return [...prev, newMessage]
      })

      // Collapse thinking, system, tool, and pre_compact messages by default
      if (
        wsMessage.message_type === 'assistant_thinking' ||
        wsMessage.message_type === 'system_message' ||
        wsMessage.message_type === 'assistant_tool_use' ||
        wsMessage.message_type === 'assistant_tool_output' ||
        wsMessage.message_type === 'assistant_pre_compact'
      ) {
        setCollapsedMessages((prev) => new Set(prev).add(wsMessage.message_id!))
      }
    })

    return () => {
      console.log('[ChatPanel] Unsubscribing from session:', currentSessionId)
      unsubscribe()
    }
  }, [currentSessionId, subscribe, selectedMosaicId, selectedNodeId, loadMessages])

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

  // Handle GeoGebra command execution
  const handleGeoGebraCommand = useCallback((payload: any) => {
    const { response_id, instance_number, commands } = payload

    if (!instance_number || !commands || !Array.isArray(commands)) {
      console.error('[ChatPanel] Invalid GeoGebra command payload:', payload)

      // Send error response if response_id exists
      if (response_id && currentSessionId) {
        sendRaw({
          session_id: currentSessionId,
          type: 'tool_response',
          response_id: response_id,
          result: {
            success: false,
            error: 'Invalid payload: missing instance_number or commands'
          }
        })
      }
      return
    }

    const api = getGeoGebraAPI(instance_number)

    if (!api) {
      console.error(`[ChatPanel] GeoGebra instance #${instance_number} not found`)

      // Send error response if response_id exists
      if (response_id && currentSessionId) {
        sendRaw({
          session_id: currentSessionId,
          type: 'tool_response',
          response_id: response_id,
          result: {
            success: false,
            error: `GeoGebra instance #${instance_number} not found`
          }
        })
      }
      return
    }

    console.log(`[ChatPanel] Executing ${commands.length} command(s) on instance #${instance_number}`)

    let executionSuccess = true
    let executionError: string | undefined = undefined

    // Execute all commands
    for (const command of commands) {
      try {
        api.evalCommand(command)
        console.log(`[ChatPanel] Successfully executed: ${command}`)
      } catch (error) {
        console.error(`[ChatPanel] Failed to execute command: ${command}`, error)
        executionSuccess = false
        executionError = error instanceof Error ? error.message : String(error)
        break // Stop on first error
      }
    }

    // Collect current state from ALL GeoGebra instances (regardless of success/failure)
    const currentStates = collectGeoGebraStates()
    console.log(`[ChatPanel] Collected states from ${currentStates.length} GeoGebra instance(s)`)

    // Send response back to backend if response_id exists
    if (response_id && currentSessionId) {
      sendRaw({
        session_id: currentSessionId,
        type: 'tool_response',
        response_id: response_id,
        result: {
          success: executionSuccess,
          current_states: currentStates,  // All instances' current states
          error: executionError
        }
      })

      const totalObjects = currentStates.reduce((sum, state) => sum + state.objects.length, 0)
      console.log(`[ChatPanel] Sent tool_response for response_id: ${response_id}, ${currentStates.length} instance(s), ${totalObjects} total objects`)
    }
  }, [currentSessionId, sendRaw, editor])

  // Collect GeoGebra states from all instances
  const collectGeoGebraStates = useCallback((): GeoGebraInstanceState[] => {
    if (!editor) {
      return []
    }

    const states: GeoGebraInstanceState[] = []

    // Get all GeoGebra shapes from the editor
    const shapes = editor.getCurrentPageShapes()
    const geogebraShapes = shapes.filter((shape: any) => shape.type === 'geogebra')

    for (const shape of geogebraShapes) {
      const instanceNumber = shape.props.instanceNumber
      const api = getGeoGebraAPI(instanceNumber)

      if (!api) {
        console.warn(`[ChatPanel] No API found for instance #${instanceNumber}`)
        continue
      }

      try {
        // Get all object names
        const objectNames = api.getAllObjectNames()
        const objects: GeoGebraObject[] = []

        for (const name of objectNames) {
          const type = api.getObjectType(name)
          const obj: GeoGebraObject = {
            name,
            type,
            definition: api.getDefinitionString(name) || '',
          }

          // Add coordinates for points and vectors
          if (type === 'point' || type === 'vector') {
            obj.x = api.getXcoord(name)
            obj.y = api.getYcoord(name)
          }

          objects.push(obj)
        }

        states.push({
          instanceNumber,
          objects,
        })
      } catch (error) {
        console.error(`[ChatPanel] Error collecting state for instance #${instanceNumber}:`, error)
      }
    }

    return states
  }, [editor])

  // Handle send message
  const handleSendMessage = useCallback((sessionId: string, message: string) => {
    if (!message.trim() || !isConnected) {
      console.warn('[ChatPanel] Cannot send: invalid message or not connected')
      return
    }

    // Collect GeoGebra states
    const geogebraStates = collectGeoGebraStates()

    // Build context
    const context: MessageContext = {}
    if (geogebraStates.length > 0) {
      context.geogebra_states = geogebraStates
      console.log('[ChatPanel] Collected GeoGebra states:', geogebraStates)
    }

    console.log('[ChatPanel] Sending message:', message, 'with context:', context)
    sendMessage(sessionId, message, Object.keys(context).length > 0 ? context : undefined)

    // Clear input after sending
    setSessionInput('')
  }, [isConnected, sendMessage, collectGeoGebraStates])

  // Handle interrupt
  const handleInterrupt = useCallback((sessionId: string) => {
    console.log('[ChatPanel] Interrupt requested for session:', sessionId)
    interrupt(sessionId)
  }, [interrupt])

  // Handle input change
  const handleInputChange = useCallback((sessionId: string, value: string) => {
    setSessionInput(value)
  }, [])

  // Handle create new session
  const handleCreateNewSession = useCallback(async () => {
    if (!selectedMosaicId || !selectedNodeId || isCreatingSession) {
      return
    }

    setIsCreatingSession(true)

    try {
      // Step 1: Close current session if it exists and is active
      if (currentSessionId && currentSessionStatus === SessionStatus.ACTIVE) {
        console.log('[ChatPanel] Closing current session:', currentSessionId)
        try {
          await apiClient.closeSession(selectedMosaicId, selectedNodeId, currentSessionId)
          console.log('[ChatPanel] Current session closed successfully')
        } catch (error) {
          console.error('[ChatPanel] Failed to close current session:', error)
          // Continue to create new session even if close fails
        }
      }

      // Step 2: Create new session
      const session = await apiClient.createSession(selectedMosaicId, selectedNodeId, {
        mode: SessionMode.CHAT,
      })
      console.log('[ChatPanel] New session created:', session.session_id)

      // Clear current state
      setCurrentSessionId(session.session_id)
      setCurrentSessionStatus(session.status)
      setCurrentRuntimeStatus(session.runtime_status || RuntimeStatus.IDLE)
      setMessages([])
      hasLoadedRef.current = false
      maxSequenceRef.current = 0
    } catch (error) {
      console.error('[ChatPanel] Failed to create new session:', error)
    } finally {
      setIsCreatingSession(false)
    }
  }, [selectedMosaicId, selectedNodeId, currentSessionId, currentSessionStatus, isCreatingSession])

  return (
    <>
      {/* Collapsed state button */}
      {!isVisible && (
        <button
          onClick={onToggle}
          className="fixed right-0 top-1/2 -translate-y-1/2 z-20 bg-white text-muted-foreground hover:text-foreground transition-colors flex items-center px-0.5 py-1.5 rounded shadow-md border border-gray-200"
          title="展开几何画板助手"
        >
          <ChevronRight className="h-4 w-4 rotate-180" />
        </button>
      )}

      {/* Chat Panel */}
      {isVisible && (
        <div className="w-[400px] border-l flex flex-col bg-background h-full relative">
          {/* Toggle button on left edge of panel */}
          <button
            onClick={onToggle}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 z-20 bg-white text-muted-foreground hover:text-foreground transition-colors flex items-center px-0.5 py-1.5 rounded shadow-md border border-gray-200"
            title="折叠面板"
          >
            <ChevronRight className="h-4 w-4" />
          </button>

          {/* Header */}
          <div className="border-b px-3 py-2 shrink-0">
            <div className="flex items-center justify-between gap-2 min-w-0">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary shrink-0" />
                <h2 className="font-semibold text-sm whitespace-nowrap">几何画板助手</h2>
              </div>
              <div className="flex items-center gap-1">
                <NodeSelector onNodeSelect={handleNodeSelect} />
                {/* New Session Button */}
                {selectedNodeId && (
                  <button
                    onClick={handleCreateNewSession}
                    disabled={isCreatingSession || isLoadingSession}
                    className="flex items-center justify-center p-0.5 bg-white border border-input hover:bg-accent hover:text-accent-foreground rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors aspect-square"
                    title="创建新会话"
                  >
                    <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Chat history - Using MessageList component */}
          <MessageList
            messages={messages}
            collapsedMessages={collapsedMessages}
            isLoading={isLoading}
            isVisible={isVisible}
            onToggleCollapse={toggleCollapse}
            sessionId={currentSessionId || ''}
          />

          {/* Input area - Using ChatInput component */}
          <ChatInput
            sessionId={currentSessionId}
            initialValue={sessionInput}
            isBusy={currentRuntimeStatus === RuntimeStatus.BUSY}
            isConnected={isConnected}
            canSendMessage={
              !isCreatingSession &&
              !isLoadingSession &&
              !!currentSessionId &&
              !!selectedNodeId &&
              currentSessionStatus === SessionStatus.ACTIVE
            }
            placeholder={
              !isConnected
                ? 'WebSocket 连接中...'
                : !selectedNodeId
                ? '请先选择一个节点...'
                : isLoadingSession
                ? '加载会话中...'
                : isCreatingSession
                ? '会话创建中...'
                : !currentSessionId
                ? '未找到会话，请创建新会话...'
                : currentSessionStatus === SessionStatus.CLOSED
                ? '此会话已关闭，请创建新会话...'
                : currentSessionStatus === SessionStatus.ARCHIVED
                ? '此会话已归档，请创建新会话...'
                : '输入消息与 AI 对话... (Ctrl+Enter 发送)'
            }
            onSendMessage={handleSendMessage}
            onInterrupt={handleInterrupt}
            onInputChange={handleInputChange}
          />
        </div>
      )}
    </>
  )
}
