"use client"

import { useState, useCallback, useEffect } from "react"
import { useParams } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Network, X, AlertCircle } from "lucide-react"
import { useWebSocket } from "@/contexts/websocket-context"
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  applyNodeChanges,
  applyEdgeChanges,
  NodeChange,
  EdgeChange,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { getLayoutedNodes } from "@/lib/layout"
import { apiClient } from "@/lib/api"
import { SessionTopologyNode, SessionStatus } from "@/lib/types"
import { useToast } from "@/hooks/use-toast"

// Session status colors
const getStatusColor = (status: SessionStatus | string) => {
  switch (status) {
    case 'active':
    case 'ACTIVE':
      return { bg: '#10b981', border: '#059669', text: '#ffffff' }
    case 'closed':
    case 'CLOSED':
      return { bg: '#6b7280', border: '#4b5563', text: '#ffffff' }
    case 'archived':
    case 'ARCHIVED':
      return { bg: '#94a3b8', border: '#64748b', text: '#ffffff' }
    default:
      return { bg: '#3b82f6', border: '#2563eb', text: '#ffffff' }
  }
}

// Flatten tree to list for ReactFlow processing
const flattenTree = (node: SessionTopologyNode): SessionTopologyNode[] => {
  const result: SessionTopologyNode[] = [node]

  for (const child of node.children) {
    result.push(...flattenTree(child))
  }

  return result
}

export default function SessionTopologyPage() {
  const params = useParams()
  const mosaicId = params.mosaicId as string
  const { toast } = useToast()
  const { subscribe } = useWebSocket()

  // Filter state
  const [sessionIdFilter, setSessionIdFilter] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Topology data
  const [topologyData, setTopologyData] = useState<{
    rootSession: SessionTopologyNode
    totalNodes: number
    maxDepth: number
  } | null>(null)

  // ReactFlow states
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])

  // Fetch topology function (extracted to be reused by WebSocket listener)
  const fetchTopology = useCallback(async () => {
    if (!sessionIdFilter.trim()) {
      setTopologyData(null)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.getSessionTopology(
        parseInt(mosaicId),
        sessionIdFilter.trim()
      )

      setTopologyData({
        rootSession: response.root_session,
        totalNodes: response.total_nodes,
        maxDepth: response.max_depth
      })
    } catch (err: any) {
      console.error("Failed to fetch session topology:", err)
      setError(err.message || "Failed to fetch session topology")
      setTopologyData(null)
      toast({
        title: "Error",
        description: err.message || "Failed to fetch session topology",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }, [mosaicId, sessionIdFilter, toast])

  // Auto-fetch topology when sessionIdFilter changes
  useEffect(() => {
    fetchTopology()
  }, [fetchTopology])

  // Listen for WebSocket session lifecycle events to refresh topology
  useEffect(() => {
    const unsubscribe = subscribe('*', (message) => {
      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        return
      }

      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Handle notification messages (session lifecycle events)
      if (wsMessage.role === "notification") {
        // Only refresh if sessionIdFilter is filled
        if (!sessionIdFilter.trim()) {
          return
        }

        console.log("[SessionTopology] Received global notification:", wsMessage.message_type)

        if (wsMessage.message_type === "session_started") {
          console.log("[SessionTopology] Session started, refreshing topology")
          fetchTopology()
        }

        if (wsMessage.message_type === "session_ended") {
          console.log("[SessionTopology] Session ended, refreshing topology")
          fetchTopology()
        }
      }
    })

    return () => {
      unsubscribe()
    }
  }, [subscribe, sessionIdFilter, fetchTopology])

  // Convert topology data to ReactFlow nodes and edges
  useEffect(() => {
    if (!topologyData) {
      setNodes([])
      setEdges([])
      return
    }

    // Flatten tree to list
    const flatSessions = flattenTree(topologyData.rootSession)

    // Create nodes
    const nodeList: Node[] = flatSessions.map(session => {
      const colors = getStatusColor(session.status)
      const isRoot = !session.parent_session_id

      return {
        id: session.session_id,
        type: "default",
        data: {
          label: (
            <div
              title={`Session ID: ${session.session_id}\nNode: ${session.node_id}\nStatus: ${session.status}\nDepth: ${session.depth}`}
              style={{
                padding: '10px 14px',
                minWidth: '160px',
                maxWidth: '200px',
                textAlign: 'center'
              }}
            >
              <div style={{
                fontWeight: 700,
                fontSize: '12px',
                marginBottom: '6px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {session.node_id}
              </div>
              <div
                title={session.session_id}
                style={{
                  fontSize: '9px',
                  opacity: 0.85,
                  fontFamily: 'monospace',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}
              >
                {session.session_id.substring(0, 16)}...
              </div>
            </div>
          )
        },
        position: { x: 0, y: 0 },
        style: {
          background: colors.bg,
          color: colors.text,
          border: `${isRoot ? 3 : 2}px solid ${colors.border}`,
          borderRadius: 8,
          padding: 0,
          minWidth: 160,
          maxWidth: 200,
          fontSize: 11,
          boxShadow: isRoot
            ? '0 4px 12px rgba(0,0,0,0.25)'
            : '0 2px 6px rgba(0,0,0,0.15)'
        },
      }
    })

    // Create edges
    const edgeList: Edge[] = flatSessions
      .filter(session => session.parent_session_id)
      .map(session => ({
        id: `edge-${session.parent_session_id}-${session.session_id}`,
        source: session.parent_session_id!,
        target: session.session_id,
        type: 'smoothstep',
        animated: session.status === 'active' || session.status === 'ACTIVE',
        style: {
          stroke: '#94a3b8',
          strokeWidth: 2
        },
        markerEnd: {
          type: 'arrowclosed' as const,
          color: '#94a3b8',
          width: 20,
          height: 20
        },
      }))

    // Apply dagre layout
    const layouted = getLayoutedNodes(nodeList, edgeList, "TB")

    setNodes(layouted)
    setEdges(edgeList)
  }, [topologyData])

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds))
    },
    []
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds))
    },
    []
  )

  const handleClearFilter = () => {
    setSessionIdFilter("")
  }

  return (
    <div className="flex flex-col h-full space-y-6 overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0">
        <h1 className="text-3xl font-bold">会话拓扑可视化</h1>
        <p className="text-muted-foreground mt-1">输入根会话 ID 查看会话调用树</p>
      </div>

      {/* Search Input */}
      <div className="flex-shrink-0 flex justify-end">
        <div className="relative w-1/2">
          <Input
            placeholder="输入会话 ID..."
            value={sessionIdFilter}
            onChange={(e) => setSessionIdFilter(e.target.value)}
            className="pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          {sessionIdFilter && (
            <button
              onClick={handleClearFilter}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Graph Area */}
      <div className="flex-1 min-h-0">
        {error ? (
          <Card className="h-full flex flex-col items-center justify-center">
            <AlertCircle className="h-16 w-16 text-destructive mb-4" />
            <h2 className="text-xl font-semibold mb-2">加载失败</h2>
            <p className="text-muted-foreground text-center max-w-md">
              {error}
            </p>
          </Card>
        ) : !topologyData ? (
          <Card className="h-full flex flex-col items-center justify-center">
            <Network className="h-16 w-16 text-muted-foreground mb-4" />
            <h2 className="text-xl font-semibold mb-2">请输入会话 ID</h2>
            <p className="text-muted-foreground text-center max-w-md">
              在上方输入框中输入一个会话 ID 作为根节点，查看其调用树
            </p>
          </Card>
        ) : (
          <Card className="h-full">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
              nodesDraggable={true}
              nodesConnectable={false}
              elementsSelectable={true}
              className="bg-background"
              minZoom={0.1}
              maxZoom={2}
            >
              <Background />
              <Controls />
              <MiniMap
                nodeColor={(node) => {
                  const flatSessions = flattenTree(topologyData.rootSession)
                  const session = flatSessions.find(s => s.session_id === node.id)
                  return session ? getStatusColor(session.status).bg : '#3b82f6'
                }}
                pannable
                zoomable
              />
            </ReactFlow>
          </Card>
        )}
      </div>

      {/* Legend */}
      {topologyData && (
        <div className="flex-shrink-0 flex items-center gap-6 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#10b981' }}></div>
            <span>活跃 (ACTIVE)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#6b7280' }}></div>
            <span>已关闭 (CLOSED)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#94a3b8' }}></div>
            <span>已归档 (ARCHIVED)</span>
          </div>
          <div className="ml-auto">
            共 {topologyData.totalNodes} 个会话节点 | 最大深度: {topologyData.maxDepth}
          </div>
        </div>
      )}
    </div>
  )
}
