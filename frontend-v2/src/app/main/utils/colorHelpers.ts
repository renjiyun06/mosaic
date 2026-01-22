/**
 * Color utility functions for event types and nodes
 */

import type { EventTypeColor } from "../types"

/**
 * Get color configuration for event type
 * @param eventType - The event type string
 * @returns Color configuration object
 */
export const getEventTypeColor = (eventType: string): EventTypeColor => {
  switch (eventType) {
    case "node_message":
      return { stroke: "#22d3ee", fill: "#22d3ee", text: "cyan" } // Cyan
    case "system_message":
      return { stroke: "#a855f7", fill: "#a855f7", text: "purple" } // Purple
    case "task_complete":
      return { stroke: "#10b981", fill: "#10b981", text: "emerald" } // Green
    default:
      return { stroke: "#22d3ee", fill: "#22d3ee", text: "cyan" }
  }
}

/**
 * Legend items for topology visualization
 */
export const LEGEND_ITEMS = [
  { label: "Node Message", color: "#22d3ee", eventType: "node_message" },
  { label: "System Message", color: "#a855f7", eventType: "system_message" },
  { label: "Task Complete", color: "#10b981", eventType: "task_complete" },
]
