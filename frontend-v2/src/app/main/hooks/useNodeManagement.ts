/**
 * Node management hook - handles node/edge state and operations
 */

import { useState, useEffect, useCallback } from "react"
import type { Node, Edge } from "@xyflow/react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import type { NodeOut, ConnectionOut } from "@/lib/types"
import { transformApiNodesToFlowNodes, getConnectionsForNode } from "../utils"
import { mockConnections } from "../constants"

export function useNodeManagement(currentMosaicId: number | null) {
  const { token } = useAuth()
  const [apiNodes, setApiNodes] = useState<NodeOut[]>([])
  const [apiConnections, setApiConnections] = useState<ConnectionOut[]>([])
  const [loadingNodes, setLoadingNodes] = useState(false)
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>(
    mockConnections.map((conn) => ({
      id: `e${conn.from}-${conn.to}`,
      source: conn.from,
      target: conn.to,
      type: "animated",
      animated: true,
      data: {
        eventType: conn.eventType,
        showTopology: false,
      },
    }))
  )

  // Load nodes and connections when Mosaic changes
  useEffect(() => {
    const loadMosaicData = async () => {
      if (!currentMosaicId || !token) {
        setNodes([])
        setApiNodes([])
        setApiConnections([])
        return
      }

      try {
        setLoadingNodes(true)
        const [nodesData, connectionsData] = await Promise.all([
          apiClient.listNodes(currentMosaicId),
          apiClient.listConnections(currentMosaicId),
        ])

        setApiNodes(nodesData)
        setApiConnections(connectionsData)

        // Transform API nodes to ReactFlow nodes
        const flowNodes = transformApiNodesToFlowNodes(nodesData)
        setNodes(flowNodes)
      } catch (error) {
        console.error("Failed to load mosaic data:", error)
      } finally {
        setLoadingNodes(false)
      }
    }

    loadMosaicData()
  }, [currentMosaicId, token])

  // Create new node
  const handleCreateNode = useCallback((nodeData: any) => {
    const newNodeId = String(nodes.length + 1)
    const newNode: Node = {
      id: newNodeId,
      type: "collapsedNode",
      position: { x: 400, y: 300 }, // Center-ish position
      data: {
        nodeId: newNodeId,
        id: nodeData.id,
        type: nodeData.type === "claude_code" ? "Claude Code" : nodeData.type,
        status: nodeData.autoStart ? "running" : "stopped",
        sessions: 0,
        messages: 0,
        activity: 0,
        expanded: false,
        incomingConnections: 0,
        outgoingConnections: 0,
      },
    }
    setNodes((nds) => [...nds, newNode])
  }, [nodes.length])

  // Toggle node expansion
  const toggleNodeExpansion = useCallback((nodeId: string) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const isExpanding = !node.data.expanded
          return {
            ...node,
            type: isExpanding ? "expandedNode" : "collapsedNode",
            data: {
              ...node.data,
              expanded: isExpanding,
              onExpand: () => toggleNodeExpansion(nodeId),
              onCollapse: () => toggleNodeExpansion(nodeId),
            },
          }
        }
        return {
          ...node,
          data: {
            ...node.data,
            onExpand: () => toggleNodeExpansion(node.id),
            onCollapse: () => toggleNodeExpansion(node.id),
          },
        }
      })
    )
  }, [])

  // Initialize node handlers and connection counts
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const { incomingCount, outgoingCount } = getConnectionsForNode(node.id, apiConnections)
        return {
          ...node,
          data: {
            ...node.data,
            incomingConnections: incomingCount,
            outgoingConnections: outgoingCount,
            onExpand: () => toggleNodeExpansion(node.id),
            onCollapse: () => toggleNodeExpansion(node.id),
            onShowConnections: (direction: "incoming" | "outgoing") => {
              console.log(`Show ${direction} connections for ${node.data.id}`)
            },
          },
        }
      })
    )
  }, [toggleNodeExpansion, apiConnections])

  return {
    apiNodes,
    apiConnections,
    loadingNodes,
    nodes,
    edges,
    setNodes,
    setEdges,
    handleCreateNode,
    toggleNodeExpansion,
  }
}
