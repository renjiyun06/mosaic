"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader2, Download } from "lucide-react"
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
  EdgeTypes,
  useReactFlow,
  ReactFlowProvider,
  getNodesBounds,
  getViewportForBounds
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import CustomEdge from "@/components/custom-edge"
import { toPng, toSvg } from "html-to-image"

// Define custom edge types
const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
}

// Node type display labels
const getNodeTypeLabel = (nodeType: string): string => {
  const labels: Record<string, string> = {
    'claude_code': 'Claude Code',
    'scheduler': 'Scheduler',
    'email': 'Email'
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

function TopologyContent() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string
  const { getNodes, getEdges, getViewport } = useReactFlow()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [topologyNodes, setTopologyNodes] = useState<Node[]>([])
  const [topologyEdges, setTopologyEdges] = useState<Edge[]>([])
  const [isMobile, setIsMobile] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportFormat, setExportFormat] = useState<'svg' | 'png' | null>(null)

  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 640)
    }

    checkMobile()
    window.addEventListener('resize', checkMobile)

    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Handle node changes (for dragging)
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setTopologyNodes((nds) => applyNodeChanges(changes, nds))
    },
    []
  )

  // Export topology as PNG with high quality
  const handleExportPNG = useCallback(async () => {
    try {
      setIsExporting(true)
      setExportFormat('png')

      // Wait a bit to ensure rendering is complete
      await new Promise(resolve => setTimeout(resolve, 100))

      const viewportElement = document.querySelector('.react-flow__viewport') as HTMLElement

      if (!viewportElement) {
        console.error('Viewport element not found')
        return
      }

      // Get current nodes to calculate bounds
      const nodes = getNodes()

      // Calculate the bounds of all nodes
      const nodesBounds = getNodesBounds(nodes)

      // Calculate dimensions with padding
      const imageWidth = nodesBounds.width + 100
      const imageHeight = nodesBounds.height + 100

      // Get viewport transform to fit all nodes
      const viewport = getViewportForBounds(
        nodesBounds,
        imageWidth,
        imageHeight,
        0.5, // min zoom
        2,   // max zoom
        0.1  // padding
      )

      // Use toPng for high-quality PNG export
      const dataUrl = await toPng(viewportElement, {
        backgroundColor: 'white',
        quality: 0.95,
        width: imageWidth,
        height: imageHeight,
        style: {
          transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`
        },
        filter: (node: Element) => {
          // Filter out controls and minimap
          const classNames = node.className?.toString() || ''
          return !classNames.includes('react-flow__controls') &&
                 !classNames.includes('react-flow__minimap')
        }
      })

      // Download the PNG
      const link = document.createElement('a')
      link.download = `topology-${mosaicId}.png`
      link.href = dataUrl
      link.click()

      console.log('PNG export successful')
    } catch (error) {
      console.error('Failed to export topology as PNG:', error)
      alert('PNG导出失败，请查看控制台了解详细信息')
    } finally {
      setIsExporting(false)
      setExportFormat(null)
    }
  }, [mosaicId, getNodes])

  // Export topology as SVG - simplified version
  const handleExportSVG = useCallback(async () => {
    try {
      setIsExporting(true)
      setExportFormat('svg')

      // Wait a bit to ensure rendering is complete
      await new Promise(resolve => setTimeout(resolve, 100))

      const viewportElement = document.querySelector('.react-flow__viewport') as HTMLElement

      if (!viewportElement) {
        console.error('Viewport element not found')
        return
      }

      // Get current nodes to calculate bounds
      const nodes = getNodes()

      // Calculate the bounds of all nodes
      const nodesBounds = getNodesBounds(nodes)

      // Calculate dimensions with padding
      const imageWidth = nodesBounds.width + 100
      const imageHeight = nodesBounds.height + 100

      // Get viewport transform to fit all nodes
      const viewport = getViewportForBounds(
        nodesBounds,
        imageWidth,
        imageHeight,
        0.5, // min zoom
        2,   // max zoom
        0.1  // padding
      )

      console.log('Exporting SVG with html-to-image...')

      // Export using html-to-image directly
      const dataUrl = await toSvg(viewportElement, {
        backgroundColor: 'white',
        width: imageWidth,
        height: imageHeight,
        style: {
          transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`
        },
        filter: (node: Element) => {
          // Filter out controls and minimap
          const classNames = node.className?.toString() || ''
          return !classNames.includes('react-flow__controls') &&
                 !classNames.includes('react-flow__minimap')
        }
      })

      // Download the SVG
      const link = document.createElement('a')
      link.download = `topology-${mosaicId}.svg`
      link.href = dataUrl
      link.click()

      console.log('SVG export successful')
    } catch (error) {
      console.error('Failed to export topology as SVG:', error)
      alert('SVG导出失败，请查看控制台了解详细信息')
    } finally {
      setIsExporting(false)
      setExportFormat(null)
    }
  }, [mosaicId, getNodes])

  // Load topology data from API
  useEffect(() => {
    if (!token) return

    const fetchTopology = async () => {
      try {
        setLoading(true)
        setError(null)
        const topology = await apiClient.getTopology(Number(mosaicId))

        // Responsive sizing
        const nodeMaxWidth = isMobile ? '140px' : '180px'
        const nodeFontSize = isMobile ? '10px' : '11px'
        const nodeTypeFontSize = isMobile ? '8px' : '9px'
        const nodePadding = isMobile ? 6 : 8
        const nodeMinWidth = isMobile ? 80 : 100
        const nodeMinHeight = isMobile ? 38 : 45

        // Convert nodes to React Flow nodes
        const initialNodes: Node[] = topology.nodes.map((node) => ({
          id: node.node_id,
          type: "default",
          data: {
            label: (
              <div
                style={{
                  overflow: 'hidden',
                  maxWidth: nodeMaxWidth,
                  width: '100%'
                }}
                title={`${node.node_id} (${getNodeTypeLabel(node.node_type)})`}
              >
                <div style={{
                  fontWeight: 600,
                  fontSize: nodeFontSize,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}>
                  {node.node_id}
                </div>
                <div style={{
                  fontSize: nodeTypeFontSize,
                  opacity: 0.8,
                  marginTop: '2px',
                  whiteSpace: 'nowrap'
                }}>
                  {getNodeTypeLabel(node.node_type)}
                </div>
              </div>
            )
          },
          position: { x: 0, y: 0 }, // Will be calculated by dagre
          draggable: true,
          style: {
            background: "#3b82f6",
            color: "white",
            border: "1px solid #222",
            padding: nodePadding,
            borderRadius: 4,
            minWidth: nodeMinWidth,
            maxWidth: 200,
            height: 'auto',
            minHeight: nodeMinHeight,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
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

        // Responsive edge styling
        const edgeLabelFontSize = isMobile ? 6 : 7
        const edgeStrokeWidth = isMobile ? 1.5 : 2

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
                fontSize: edgeLabelFontSize,
              },
              labelBgStyle: {
                fill: "#ffffff",
                fillOpacity: 0.9,
              },
              style: {
                stroke: "#3b82f6",
                strokeDasharray: "5,5",
                strokeWidth: edgeStrokeWidth
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
              strokeWidth: edgeStrokeWidth
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
  }, [mosaicId, token, isMobile])

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px] sm:min-h-[400px]">
        <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] sm:min-h-[400px] px-4">
        <p className="text-muted-foreground mb-4 text-sm sm:text-base text-center">{error}</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-3 sm:space-y-4 md:space-y-6">
      <div className="flex-shrink-0 flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold">拓扑可视化</h1>
          <p className="text-muted-foreground mt-1 text-sm sm:text-base">查看节点和连接关系</p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleExportSVG}
            disabled={isExporting || loading}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            {isExporting && exportFormat === 'svg' ? '导出中...' : '导出SVG'}
          </Button>
          <Button
            onClick={handleExportPNG}
            disabled={isExporting || loading}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            {isExporting && exportFormat === 'png' ? '导出中...' : '导出PNG'}
          </Button>
        </div>
      </div>

      <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <CardContent className="p-0 flex-1 overflow-hidden">
          <div className="h-full overflow-hidden">
            <ReactFlow
              nodes={topologyNodes}
              edges={topologyEdges}
              edgeTypes={edgeTypes}
              onNodesChange={onNodesChange}
              fitView
              nodesDraggable={true}
              nodesConnectable={false}
              elementsSelectable={true}
              className="bg-background touchdevice-flow"
              minZoom={0.1}
              maxZoom={2}
              panOnScroll={false}
              panOnDrag={true}
              zoomOnScroll={true}
              zoomOnPinch={true}
              zoomOnDoubleClick={true}
              preventScrolling={true}
              defaultViewport={{ x: 0, y: 0, zoom: 1 }}
            >
              <Background />
              <Controls
                showZoom={true}
                showFitView={true}
                showInteractive={false}
                position="bottom-left"
                className="!bottom-2 sm:!bottom-4 !left-2 sm:!left-4"
              />
              {/* MiniMap only visible on larger screens */}
              <MiniMap
                className="hidden lg:block"
                nodeColor="#3b82f6"
                maskColor="rgb(0, 0, 0, 0.1)"
              />
            </ReactFlow>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function TopologyPage() {
  return (
    <ReactFlowProvider>
      <TopologyContent />
    </ReactFlowProvider>
  )
}
