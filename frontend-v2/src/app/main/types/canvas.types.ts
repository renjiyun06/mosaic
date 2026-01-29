/**
 * Canvas and Node related type definitions
 */

export interface Session {
  id: string
  topic: string
  lastActivity: string
  messageCount: number
  status: "active" | "idle"
}

export interface EnhancedSession extends Session {
  sessionId: string
  runtimeStatus: "idle" | "busy"
  sessionStatus: "active" | "closed"
  inputTokens: number
  outputTokens: number
  contextPercentage: number
  model: "sonnet" | "opus" | "haiku"
  mode: "chat" | "program" | "background"
}

export interface NodeConnection {
  from: string
  to: string
  eventType: string
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
}

export interface NodeTypeConfig {
  value: string
  label: string
  icon: any
  color: string
}

export interface EventTypeColor {
  stroke: string
  fill: string
  text: string
}
