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

        // Transform API nodes to ReactFlow nodes (inject mosaicId)
        const flowNodes = transformApiNodesToFlowNodes(nodesData, currentMosaicId)
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
  const handleCreateNode = useCallback(async (nodeData: any) => {
    if (!currentMosaicId || !token) return

    try {
      // Call API to create node
      await apiClient.createNode(currentMosaicId, {
        node_id: nodeData.id,
        node_type: nodeData.type,
        description: nodeData.description,
        config: nodeData.config,
        auto_start: nodeData.autoStart,
      })

      // Refresh node list
      const nodesData = await apiClient.listNodes(currentMosaicId)
      setApiNodes(nodesData)

      // Transform and update ReactFlow nodes
      const flowNodes = transformApiNodesToFlowNodes(nodesData, currentMosaicId)
      setNodes(flowNodes)
    } catch (error) {
      console.error("Failed to create node:", error)
      throw error
    }
  }, [currentMosaicId, token])

  // Edit node
  const handleEditNode = useCallback(async (
    nodeId: string,
    data: {
      description?: string | null
      config?: Record<string, any> | null
      auto_start?: boolean | null
    }
  ) => {
    if (!currentMosaicId || !token) return

    try {
      // Call API to update node
      await apiClient.updateNode(currentMosaicId, nodeId, data)

      // Refresh node list
      const nodesData = await apiClient.listNodes(currentMosaicId)
      setApiNodes(nodesData)

      // Transform and update ReactFlow nodes
      const flowNodes = transformApiNodesToFlowNodes(nodesData, currentMosaicId)
      setNodes(flowNodes)
    } catch (error) {
      console.error("Failed to edit node:", error)
      throw error
    }
  }, [currentMosaicId, token])

  // Delete node
  const handleDeleteNode = useCallback(async (nodeId: string) => {
    if (!currentMosaicId || !token) return

    try {
      // Call API to delete node
      await apiClient.deleteNode(currentMosaicId, nodeId)

      // Refresh node list
      const nodesData = await apiClient.listNodes(currentMosaicId)
      setApiNodes(nodesData)

      // Transform and update ReactFlow nodes
      const flowNodes = transformApiNodesToFlowNodes(nodesData, currentMosaicId)
      setNodes(flowNodes)
    } catch (error) {
      console.error("Failed to delete node:", error)
      throw error
    }
  }, [currentMosaicId, token])

  // Toggle node expansion
  const toggleNodeExpansion = useCallback((nodeId: string) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const isExpanding = !node.data.expanded

          // Card dimensions (collapsed: 256x220, expanded: 900x600)
          const collapsedWidth = 256
          const collapsedHeight = 220
          const expandedWidth = 900
          const expandedHeight = 600

          // Calculate position offset to keep center point fixed
          let newPosition = { ...node.position }
          if (isExpanding) {
            // Expanding: move top-left up and left to keep center fixed
            newPosition.x -= (expandedWidth - collapsedWidth) / 2
            newPosition.y -= (expandedHeight - collapsedHeight) / 2
          } else {
            // Collapsing: move top-left down and right to keep center fixed
            newPosition.x += (expandedWidth - collapsedWidth) / 2
            newPosition.y += (expandedHeight - collapsedHeight) / 2
          }

          return {
            ...node,
            type: isExpanding ? "expandedNode" : "collapsedNode",
            position: newPosition,
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
    handleEditNode,
    handleDeleteNode,
    toggleNodeExpansion,
  }
}
