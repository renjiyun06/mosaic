"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"
import { apiClient, type TopologyResponse } from "@/lib/api"
import { useAuthStore } from "@/lib/store"
import { getLayoutedNodes } from "@/lib/layout"
import { getEventTypeLabel, EventType, getNodeTypeLabel, NodeType } from "@/lib/enums"
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  applyNodeChanges,
  NodeChange,
  EdgeTypes
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import CustomEdge from "@/components/CustomEdge"

// Define custom edge types
const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
}

export default function TopologyPage() {
  const params = useParams()
  const router = useRouter()
  const { token } = useAuthStore()
  const mosaicId = params.mosaicId as string

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [topologyNodes, setTopologyNodes] = useState<Node[]>([])
  const [topologyEdges, setTopologyEdges] = useState<Edge[]>([])

  // Handle node changes (for dragging)
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setTopologyNodes((nds) => applyNodeChanges(changes, nds))
    },
    []
  )

  // Load topology data from API
  useEffect(() => {
    if (!token) {
      router.push("/login")
      return
    }

    const fetchTopology = async () => {
      try {
        setLoading(true)
        setError(null)
        const topology = await apiClient.getTopology(Number(mosaicId), token)

        // Convert nodes to React Flow nodes (initial positions will be overridden by layout)
        const initialNodes: Node[] = topology.nodes.map((node) => ({
          id: node.id,
          type: "default",
          data: { label: `${node.node_id || node.id}\n${getNodeTypeLabel(node.type as NodeType)}` },
          position: { x: 0, y: 0 }, // Placeholder, will be calculated by dagre
          draggable: true,
          style: {
            background: "#3b82f6",
            color: "white",
            border: "1px solid #222",
            padding: 10,
            borderRadius: 8,
            width: 200,
            height: 80,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            whiteSpace: "pre-line",
          },
        }))

        // Group subscriptions by (source, target) pair to calculate offsets
        const subscriptionGroups = new Map<string, typeof topology.subscriptions>()
        topology.subscriptions.forEach((sub) => {
          const key = `${sub.source_node_id}->${sub.target_node_id}`
          if (!subscriptionGroups.has(key)) {
            subscriptionGroups.set(key, [])
          }
          subscriptionGroups.get(key)!.push(sub)
        })

        // Create a set of connections that have subscriptions
        const subscriptionPairs = new Set(subscriptionGroups.keys())

        // Create edges from subscriptions with curvature offset for multiple edges
        const subscriptionEdges: Edge[] = []
        subscriptionGroups.forEach((subs, key) => {
          const count = subs.length
          subs.forEach((sub, index) => {
            // Calculate offset for multiple edges between same nodes
            // Offset is perpendicular distance from the direct line
            const offset = count > 1 ? (index - (count - 1) / 2) : 0

            subscriptionEdges.push({
              id: `sub-${sub.source_node_id}-${sub.target_node_id}-${sub.event_type}-${index}`,
              source: sub.source_node_id,
              target: sub.target_node_id,
              type: "custom",
              animated: true,
              label: getEventTypeLabel(sub.event_type as EventType),
              // Remove sourcePosition and targetPosition to allow dynamic anchor calculation
              labelStyle: {
                fill: "#3b82f6",
                fontWeight: 600,
                fontSize: 12,
                background: "#ffffff",
                padding: "4px 8px",
                borderRadius: "4px",
                border: "1px solid #3b82f6",
              },
              labelBgStyle: {
                fill: "#ffffff",
                fillOpacity: 0.9,
              },
              labelBgPadding: [8, 4] as [number, number],
              labelBgBorderRadius: 4,
              style: { stroke: "#3b82f6", strokeDasharray: "5,5", strokeWidth: 2 },
              markerEnd: {
                type: "arrowclosed" as const,
                color: "#3b82f6",
              },
              data: { offset },
            })
          })
        })

        // Create edges from connections without subscriptions (animated dashed lines)
        const connectionOnlyEdges: Edge[] = topology.connections
          .filter((conn) => {
            const key = `${conn.source_node_id}->${conn.target_node_id}`
            return !subscriptionPairs.has(key)
          })
          .map((conn) => ({
            id: `conn-${conn.source_node_id}-${conn.target_node_id}`,
            source: conn.source_node_id,
            target: conn.target_node_id,
            type: "custom",
            animated: true,
            style: { stroke: "#6b7280", strokeDasharray: "5,5", strokeWidth: 2 },
            markerEnd: {
              type: "arrowclosed" as const,
              color: "#6b7280",
            },
            data: { offset: 0 }, // No offset for single connection edges
          }))

        // Combine all edges
        const allEdges = [...subscriptionEdges, ...connectionOnlyEdges]

        // Calculate hierarchical layout using dagre
        // Use all edges (both subscriptions and connections) for layout calculation
        // because connections also represent dependency relationships
        const layoutedNodes = getLayoutedNodes(initialNodes, allEdges, "LR")

        setTopologyNodes(layoutedNodes)
        setTopologyEdges(allEdges)
      } catch (err) {
        console.error("Failed to fetch topology:", err)
        setError(err instanceof Error ? err.message : "Failed to load topology")
        // Keep empty topology on error
        setTopologyNodes([])
        setTopologyEdges([])
      } finally {
        setLoading(false)
      }
    }

    fetchTopology()
  }, [mosaicId, token, router])

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground mb-4">{error}</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex-shrink-0">
        <h1 className="text-3xl font-bold">拓扑可视化</h1>
        <p className="text-muted-foreground mt-1">查看节点和连接关系</p>
      </div>

      <Card className="flex-1 flex flex-col min-h-0">
        <CardHeader className="flex-shrink-0">
          <CardTitle>节点拓扑图</CardTitle>
        </CardHeader>
        <CardContent className="p-0 flex-1">
          <div className="h-full">
            <ReactFlow
              nodes={topologyNodes}
              edges={topologyEdges}
              edgeTypes={edgeTypes}
              onNodesChange={onNodesChange}
              fitView
              nodesDraggable={true}
              nodesConnectable={false}
              elementsSelectable={true}
              className="bg-background"
            >
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
