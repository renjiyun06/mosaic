"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { getLayoutedNodes } from "@/lib/layout"
import type { TopologyOut } from "@/lib/types"
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
import CustomEdge from "@/components/custom-edge"

// Define custom edge types
const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
}

// Node type display labels
const getNodeTypeLabel = (nodeType: string): string => {
  const labels: Record<string, string> = {
    'claude_code': 'Claude Code'
  }
  return labels[nodeType] || nodeType
}

// Event type display labels
const getEventTypeLabel = (eventType: string): string => {
  const labels: Record<string, string> = {
    'session_start': '会话开始',
    'session_response': '会话响应',
    'user_prompt_submit': '用户提交',
    'pre_tool_use': '工具使用前',
    'post_tool_use': '工具使用后',
    'session_end': '会话结束',
    'node_message': '节点消息',
    'event_batch': '事件批次',
    'system_message': '系统消息',
    'email_message': '邮件消息',
    'scheduler_message': '调度消息',
    'reddit_scraper_message': 'Reddit消息',
    'user_message_event': '用户消息'
  }
  return labels[eventType] || eventType
}

export default function TopologyPage() {
  const params = useParams()
  const { token } = useAuth()
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
    if (!token) return

    const fetchTopology = async () => {
      try {
        setLoading(true)
        setError(null)
        const topology = await apiClient.getTopology(Number(mosaicId))

        // Convert nodes to React Flow nodes
        const initialNodes: Node[] = topology.nodes.map((node) => ({
          id: node.node_id,
          type: "default",
          data: {
            label: `${node.node_id}\n${getNodeTypeLabel(node.node_type)}`
          },
          position: { x: 0, y: 0 }, // Will be calculated by dagre
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
            const offset = count > 1 ? (index - (count - 1) / 2) : 0

            subscriptionEdges.push({
              id: `sub-${sub.source_node_id}-${sub.target_node_id}-${sub.event_type}-${index}`,
              source: sub.source_node_id,
              target: sub.target_node_id,
              type: "custom",
              animated: true,
              label: getEventTypeLabel(sub.event_type),
              labelStyle: {
                fill: "#3b82f6",
                fontWeight: 600,
                fontSize: 12,
              },
              labelBgStyle: {
                fill: "#ffffff",
                fillOpacity: 0.9,
              },
              style: {
                stroke: "#3b82f6",
                strokeDasharray: "5,5",
                strokeWidth: 2
              },
              markerEnd: {
                type: "arrowclosed" as const,
                color: "#3b82f6",
              },
              data: { offset },
            })
          })
        })

        // Create edges from connections without subscriptions
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
            style: {
              stroke: "#6b7280",
              strokeDasharray: "5,5",
              strokeWidth: 2
            },
            markerEnd: {
              type: "arrowclosed" as const,
              color: "#6b7280",
            },
            data: { offset: 0 },
          }))

        // Combine all edges
        const allEdges = [...subscriptionEdges, ...connectionOnlyEdges]

        // Calculate hierarchical layout using dagre
        const layoutedNodes = getLayoutedNodes(initialNodes, allEdges, "LR")

        setTopologyNodes(layoutedNodes)
        setTopologyEdges(allEdges)
      } catch (err) {
        console.error("Failed to fetch topology:", err)
        setError(err instanceof Error ? err.message : "Failed to load topology")
        setTopologyNodes([])
        setTopologyEdges([])
      } finally {
        setLoading(false)
      }
    }

    fetchTopology()
  }, [mosaicId, token])

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
