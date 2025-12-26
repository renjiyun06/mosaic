"use client"

/**
 * WebSocket Provider
 *
 * Provides global WebSocket context for the application.
 * Manages connection lifecycle and provides message subscription interface.
 */

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { wsManager, WebSocketMessage, MessageHandler } from '@/lib/websocket-manager'
import { useAuthStore } from '@/lib/store'

interface WebSocketContextValue {
  isConnected: boolean
  sendMessage: (sessionId: string, message: string) => void
  interruptSession: (sessionId: string) => void
  subscribe: (sessionId: string, handler: MessageHandler) => () => void
  subscribeGlobal: (handler: MessageHandler) => () => void
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { token } = useAuthStore()
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    console.log('[WebSocketProvider] useEffect triggered, token:', token ? 'present' : 'null')

    if (!token) {
      console.log('[WebSocketProvider] No token, disconnecting')
      wsManager.disconnect()
      setIsConnected(false)
      return
    }

    console.log('[WebSocketProvider] Token available, connecting')
    wsManager.connect(token)

    // Register connection state callbacks
    const unsubscribeConnect = wsManager.onConnect(() => {
      console.log('[WebSocketProvider] Connected')
      setIsConnected(true)
    })

    const unsubscribeDisconnect = wsManager.onDisconnect(() => {
      console.log('[WebSocketProvider] Disconnected')
      setIsConnected(false)
    })

    const unsubscribeError = wsManager.onError((error) => {
      console.error('[WebSocketProvider] Error:', error)
    })

    // Cleanup on unmount
    return () => {
      unsubscribeConnect()
      unsubscribeDisconnect()
      unsubscribeError()
      // Don't disconnect on every cleanup - only when token becomes null
      // This prevents rapid reconnection cycles during component re-renders
    }
  }, [token])

  const value: WebSocketContextValue = {
    isConnected,
    sendMessage: (sessionId: string, message: string) => {
      wsManager.sendMessage(sessionId, message)
    },
    interruptSession: (sessionId: string) => {
      wsManager.interruptSession(sessionId)
    },
    subscribe: (sessionId: string, handler: MessageHandler) => {
      return wsManager.subscribe(sessionId, handler)
    },
    subscribeGlobal: (handler: MessageHandler) => {
      return wsManager.subscribeGlobal(handler)
    }
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

/**
 * Hook to access WebSocket context
 */
export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider')
  }
  return context
}
