/**
 * Mock data for development and testing - Enhanced for expanded node card
 */

import type { Session, NodeConnection, ChatMessage } from "../types"

// Enhanced session type with runtime status and token stats
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

export const mockSessions: Record<string, EnhancedSession[]> = {
  "node-1": [
    {
      id: "session-1",
      sessionId: "a1b2c3d4",
      topic: "Fix login authentication bug",
      lastActivity: "2m ago",
      messageCount: 24,
      status: "active",
      runtimeStatus: "idle",
      sessionStatus: "active",
      inputTokens: 1200,
      outputTokens: 800,
      contextPercentage: 12,
      model: "sonnet",
      mode: "chat",
    },
    {
      id: "session-2",
      sessionId: "e5f6g7h8",
      topic: "Add user profile feature with avatar upload and real-time image compression",
      lastActivity: "15m ago",
      messageCount: 18,
      status: "active",
      runtimeStatus: "busy",
      sessionStatus: "active",
      inputTokens: 3500,
      outputTokens: 2100,
      contextPercentage: 45,
      model: "opus",
      mode: "program",
    },
    {
      id: "session-3",
      sessionId: "i9j0k1l2",
      topic: "Database migration completed",
      lastActivity: "1h ago",
      messageCount: 31,
      status: "idle",
      runtimeStatus: "idle",
      sessionStatus: "closed",
      inputTokens: 5200,
      outputTokens: 3000,
      contextPercentage: 68,
      model: "haiku",
      mode: "background",
    },
  ],
  "node-2": [
    {
      id: "session-4",
      sessionId: "m3n4o5p6",
      topic: "Code review session",
      lastActivity: "5m ago",
      messageCount: 12,
      status: "active",
      runtimeStatus: "idle",
      sessionStatus: "active",
      inputTokens: 800,
      outputTokens: 600,
      contextPercentage: 8,
      model: "sonnet",
      mode: "chat",
    },
  ],
  "node-3": [],
}

export const mockMessages: Record<string, ChatMessage[]> = {
  "session-1": [
    { id: "m1", role: "user", content: "Help me debug the login authentication flow", timestamp: "10:30 AM" },
    { id: "m2", role: "assistant", content: "I'll help you debug the authentication flow. Can you share the relevant code?", timestamp: "10:31 AM" },
    { id: "m3", role: "user", content: "Here's the auth middleware code:\n```typescript\nfunction authenticate(req, res, next) {\n  const token = req.headers.authorization;\n  // ...\n}\n```", timestamp: "10:32 AM" },
    { id: "m4", role: "assistant", content: "I see the issue. The token validation is missing null checks. Let me help you fix it.", timestamp: "10:33 AM" },
  ],
  "session-2": [
    { id: "m5", role: "user", content: "I need to add a user profile page with avatar upload and real-time image compression", timestamp: "11:00 AM" },
    { id: "m6", role: "assistant", content: "I'll help you implement the user profile feature with avatar upload and real-time compression. Let's start with the backend API for image handling...", timestamp: "11:01 AM" },
  ],
  "session-3": [
    { id: "m7", role: "user", content: "The database migration is complete", timestamp: "9:45 AM" },
    { id: "m8", role: "assistant", content: "Great! All tables have been migrated successfully.", timestamp: "9:46 AM" },
  ],
  "session-4": [
    { id: "m9", role: "user", content: "Please review this React component", timestamp: "12:00 PM" },
    { id: "m10", role: "assistant", content: "I'll review your component. Please share the code.", timestamp: "12:01 PM" },
  ],
}

export const mockConnections: NodeConnection[] = [
  { from: "1", to: "2", eventType: "node_message" },
  { from: "1", to: "3", eventType: "system_message" },
  { from: "2", to: "4", eventType: "node_message" },
  { from: "4", to: "2", eventType: "task_complete" },
]
