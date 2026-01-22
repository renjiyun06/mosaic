/**
 * Mock data for development and testing
 */

import type { Session, NodeConnection, ChatMessage } from "../types"

export const mockSessions: Record<string, Session[]> = {
  "1": [
    { id: "s1", topic: "Implementing API endpoints", lastActivity: "2m ago", messageCount: 24, status: "active" },
    { id: "s2", topic: "Database schema design", lastActivity: "15m ago", messageCount: 18, status: "idle" },
    { id: "s3", topic: "Frontend optimization", lastActivity: "1h ago", messageCount: 31, status: "idle" },
  ],
  "2": [
    { id: "s4", topic: "Code review session", lastActivity: "5m ago", messageCount: 12, status: "active" },
    { id: "s5", topic: "Bug fixing", lastActivity: "30m ago", messageCount: 8, status: "idle" },
  ],
  "3": [],
  "4": [
    { id: "s6", topic: "Research documentation", lastActivity: "10m ago", messageCount: 45, status: "active" },
  ],
}

export const mockMessages: Record<string, ChatMessage[]> = {
  s1: [
    { id: "m1", role: "user", content: "Help me implement a REST API endpoint", timestamp: "10:30 AM" },
    { id: "m2", role: "assistant", content: "I'll help you create a REST API endpoint. What framework are you using?", timestamp: "10:31 AM" },
    { id: "m3", role: "user", content: "Using Express.js with TypeScript", timestamp: "10:32 AM" },
  ],
  s4: [
    { id: "m4", role: "user", content: "Review this code please", timestamp: "11:00 AM" },
    { id: "m5", role: "assistant", content: "I'll review your code. Please share the code snippet.", timestamp: "11:01 AM" },
  ],
  s6: [
    { id: "m6", role: "user", content: "Search for React best practices", timestamp: "9:45 AM" },
  ],
}

export const mockConnections: NodeConnection[] = [
  { from: "1", to: "2", eventType: "node_message" },
  { from: "1", to: "3", eventType: "system_message" },
  { from: "2", to: "4", eventType: "node_message" },
  { from: "4", to: "2", eventType: "task_complete" },
]
