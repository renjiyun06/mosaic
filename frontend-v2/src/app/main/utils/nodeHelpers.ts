/**
 * Node helper functions for data transformation and calculations
 */

import type { Node } from "@xyflow/react"
import type { NodeOut, ConnectionOut } from "@/lib/types"

/**
 * Calculate incoming and outgoing connection counts for a node
 */
export const getConnectionsForNode = (nodeId: string, connections: ConnectionOut[]) => {
  const incoming = connections.filter(c => c.target_node_id === nodeId)
  const outgoing = connections.filter(c => c.source_node_id === nodeId)
  return {
    incoming,
    outgoing,
    incomingCount: incoming.length,
    outgoingCount: outgoing.length
  }
}

/**
 * Transform API nodes to ReactFlow nodes
 */
export const transformApiNodesToFlowNodes = (apiNodes: NodeOut[], mosaicId: number | null): Node[] => {
  return apiNodes.map((node, index) => ({
    id: String(node.id),
    type: "collapsedNode",
    position: { x: 100 + index * 250, y: 100 + (index % 2) * 300 },
    style: { zIndex: 1 }, // Initialize with base z-index
    data: {
      nodeId: String(node.id),
      id: node.node_id,
      type: node.node_type,
      status: node.status,
      sessions: 0, // TODO: Get from API
      messages: 0,
      activity: 0,
      expanded: false,
      mosaicId, // Inject mosaicId for session/message loading
    },
  }))
}

/**
 * Get node name from nodes array by ID
 */
export const getNodeName = (nodeId: string, nodes: Node[]): string => {
  const node = nodes.find(n => n.id === nodeId)
  return node?.data.id || nodeId
}
