"use client"

/**
 * WebSocket Context
 * Manages global WebSocket connection for real-time session communication
 */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode, useRef } from 'react'
import { useAuth } from './auth-context'
import { API_BASE_URL } from '@/lib/types'

// WebSocket message types from backend
export interface WSMessage {
  session_id: string
  role: 'user' | 'assistant' | 'system' | 'notification'
  message_type: string
  message_id?: string  // Optional: notification messages may not have message_id
  sequence: number
  timestamp: string
  payload: any
}

export interface WSError {
  session_id?: string | null
  type: 'error'
  message: string
}

// Message sent from client to server
export interface WSClientMessage {
  session_id: string
  type: 'user_message' | 'interrupt'
  message?: string
}

type MessageHandler = (message: WSMessage | WSError) => void

interface WebSocketContextType {
  isConnected: boolean
  sendMessage: (sessionId: string, message: string) => void
  interrupt: (sessionId: string) => void
  subscribe: (sessionId: string, handler: MessageHandler) => () => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

const WS_RECONNECT_DELAY = 3000 // 3 seconds
const WS_MAX_RECONNECT_ATTEMPTS = 5

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { token, isAuthenticated } = useAuth()
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const handlersRef = useRef<Map<string, Set<MessageHandler>>>(new Map())
  const isManualCloseRef = useRef(false)

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!token || !isAuthenticated || typeof window === 'undefined') {
      return
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    try {
      // Construct WebSocket URL from API_BASE_URL
      // Convert http://localhost:18888 to ws://localhost:18888
      const wsBaseUrl = API_BASE_URL.replace(/^http/, 'ws')
      const wsUrl = `${wsBaseUrl}/api/ws/user?token=${encodeURIComponent(token)}`

      console.log('[WebSocket] Connecting to:', wsUrl.replace(token, '***'))

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSMessage | WSError
          console.log('[WebSocket] Message received:', data)

          // Route message to session-specific handlers
          const sessionId = data.session_id
          if (sessionId && handlersRef.current.has(sessionId)) {
            const handlers = handlersRef.current.get(sessionId)!
            handlers.forEach(handler => {
              try {
                handler(data)
              } catch (error) {
                console.error('[WebSocket] Handler error:', error)
              }
            })
          }

          // Also call global handlers (session_id = '*')
          if (handlersRef.current.has('*')) {
            const handlers = handlersRef.current.get('*')!
            handlers.forEach(handler => {
              try {
                handler(data)
              } catch (error) {
                console.error('[WebSocket] Global handler error:', error)
              }
            })
          }
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
      }

      ws.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason)
        setIsConnected(false)
        wsRef.current = null

        // Auto-reconnect if not a manual close and still authenticated
        if (!isManualCloseRef.current && isAuthenticated && reconnectAttemptsRef.current < WS_MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++
          console.log(`[WebSocket] Reconnecting (attempt ${reconnectAttemptsRef.current}/${WS_MAX_RECONNECT_ATTEMPTS})...`)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, WS_RECONNECT_DELAY)
        } else if (reconnectAttemptsRef.current >= WS_MAX_RECONNECT_ATTEMPTS) {
          console.error('[WebSocket] Max reconnection attempts reached')
        }
      }
    } catch (error) {
      console.error('[WebSocket] Connection error:', error)
    }
  }, [token, isAuthenticated])

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    isManualCloseRef.current = true

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      console.log('[WebSocket] Disconnecting...')
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
    reconnectAttemptsRef.current = 0
  }, [])

  // Connect/disconnect based on auth state
  useEffect(() => {
    if (isAuthenticated && token) {
      isManualCloseRef.current = false
      connect()
    } else {
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [isAuthenticated, token, connect, disconnect])

  // Send user message to session
  const sendMessage = useCallback((sessionId: string, message: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WebSocket] Cannot send message: not connected')
      return
    }

    const payload: WSClientMessage = {
      session_id: sessionId,
      type: 'user_message',
      message
    }

    console.log('[WebSocket] Sending message:', payload)
    wsRef.current.send(JSON.stringify(payload))
  }, [])

  // Send interrupt to session
  const interrupt = useCallback((sessionId: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WebSocket] Cannot send interrupt: not connected')
      return
    }

    const payload: WSClientMessage = {
      session_id: sessionId,
      type: 'interrupt'
    }

    console.log('[WebSocket] Sending interrupt:', payload)
    wsRef.current.send(JSON.stringify(payload))
  }, [])

  // Subscribe to messages for a specific session
  const subscribe = useCallback((sessionId: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(sessionId)) {
      handlersRef.current.set(sessionId, new Set())
    }
    handlersRef.current.get(sessionId)!.add(handler)

    console.log(`[WebSocket] Subscribed to session: ${sessionId}`)

    // Return unsubscribe function
    return () => {
      const handlers = handlersRef.current.get(sessionId)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          handlersRef.current.delete(sessionId)
        }
      }
      console.log(`[WebSocket] Unsubscribed from session: ${sessionId}`)
    }
  }, [])

  const value: WebSocketContextType = {
    isConnected,
    sendMessage,
    interrupt,
    subscribe
  }

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>
}

export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}
