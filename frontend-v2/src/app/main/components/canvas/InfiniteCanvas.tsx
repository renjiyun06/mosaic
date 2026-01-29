/**
 * Infinite Canvas - Main canvas component integrating all features
 */

import { useCallback, useEffect, useState } from "react"
import {
  ReactFlow,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  BackgroundVariant,
  type Node,
  type NodeChange,
  type EdgeChange,
  type Connection,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { AnimatePresence, motion } from "framer-motion"
import {
  useMosaicManagement,
  useNodeManagement,
  useCanvasState,
  useKeyboardShortcuts,
} from "../../hooks"
import {
  MosaicSidebar,
  MosaicDialog,
} from "../mosaic"
import {
  CollapsedNodeCard,
  ExpandedNodeCard,
  CreateNodeCard,
  CreateSessionDialog,
  EditNodeDialog,
  DeleteNodeDialog,
  edgeTypes,
} from "../nodes"
import {
  TopologyLegend,
  CanvasContextMenu,
  TopRightActions,
  CanvasBackground,
} from "./"
import {
  ConnectionsSidebar,
  ConnectionConfigPanel,
  SubscriptionManagementPanel,
  TargetNodeSelectionDialog,
  CreateConnectionDialog,
} from "../connections"
import {
  CommandPalette,
} from "../command"
import {
  LoadingScreen,
  AmbientParticles,
} from "../shared"
import { mockConnections } from "../../constants"
import { useWebSocket } from "@/contexts/websocket-context"
import { apiClient } from "@/lib/api"

// Node types configuration
const nodeTypes = {
  collapsedNode: CollapsedNodeCard,
  expandedNode: ExpandedNodeCard,
}

export function InfiniteCanvas() {
  // Custom Hooks
  const mosaicManagement = useMosaicManagement()
  const nodeManagement = useNodeManagement(mosaicManagement.currentMosaicId)
  const canvasState = useCanvasState()
  const { subscribe } = useWebSocket()

  // Connection configuration state (kept for backward compatibility)
  const [pendingConnection, setPendingConnection] = useState<{
    source: string
    target: string
  } | null>(null)

  // Connection creation state - unified dialog
  const [createConnectionOpen, setCreateConnectionOpen] = useState(false)

  // Subscription management state
  const [subscriptionPanelOpen, setSubscriptionPanelOpen] = useState(false)
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null)
  const [selectedConnectionNodes, setSelectedConnectionNodes] = useState<{
    source: string
    target: string
  } | null>(null)

  // Node edit/delete state
  const [editNodeDialogOpen, setEditNodeDialogOpen] = useState(false)
  const [deleteNodeDialogOpen, setDeleteNodeDialogOpen] = useState(false)
  const [selectedNodeForAction, setSelectedNodeForAction] = useState<{
    id: string
    name?: string
    description?: string | null
    config?: Record<string, any> | null
    autoStart?: boolean
    activeSessions?: number
    incomingConnections?: number
    outgoingConnections?: number
  } | null>(null)

  // Create session state
  const [createSessionDialogOpen, setCreateSessionDialogOpen] = useState(false)
  const [selectedNodeForSession, setSelectedNodeForSession] = useState<string | null>(null)
  const [newlyCreatedSession, setNewlyCreatedSession] = useState<{
    nodeId: string
    sessionId: string
  } | null>(null)

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onOpenCommand: () => canvasState.setCommandOpen(true),
    onCloseCommand: () => canvasState.setCommandOpen(false),
  })

  // Global notification listener - Listen for session lifecycle events
  useEffect(() => {
    const unsubscribe = subscribe('*', (message) => {
      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        return
      }

      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Only handle notification messages
      if (wsMessage.role !== "notification") {
        return
      }

      console.log("[InfiniteCanvas] Received notification:", wsMessage.message_type, wsMessage.payload)

      // Handle different notification types
      switch (wsMessage.message_type) {
        case "session_started":
          console.log("[InfiniteCanvas] Session started, refreshing nodes")
          nodeManagement.refreshNodes()
          break

        case "session_ended":
          console.log("[InfiniteCanvas] Session ended, refreshing nodes")
          nodeManagement.refreshNodes()
          break

        case "topic_updated":
          console.log("[InfiniteCanvas] Topic updated, refreshing nodes")
          nodeManagement.refreshNodes()
          break

        case "runtime_status_changed":
          console.log("[InfiniteCanvas] Runtime status changed, refreshing nodes")
          nodeManagement.refreshNodes()
          break

        default:
          console.log("[InfiniteCanvas] Unknown notification type:", wsMessage.message_type)
      }
    })

    return () => {
      unsubscribe()
    }
  }, [subscribe, nodeManagement.refreshNodes])

  // Update edges visibility based on topology toggle
  useEffect(() => {
    nodeManagement.setEdges((eds) =>
      eds.map((edge) => ({
        ...edge,
        data: {
          ...edge.data,
          showTopology: canvasState.showTopology,
        },
      }))
    )
  }, [canvasState.showTopology, nodeManagement.setEdges])

  // Inject edit/delete/createSession handlers and newlyCreatedSession into nodes
  useEffect(() => {
    if (newlyCreatedSession) {
      console.log("[InfiniteCanvas] Injecting newlyCreatedSessionId into nodes:", newlyCreatedSession)
      console.log("[InfiniteCanvas] Current nodes:", nodeManagement.nodes.map(n => ({ id: n.id, type: n.type, expanded: n.data?.expanded })))
    }

    nodeManagement.setNodes((nds) =>
      nds.map((node) => {
        // Match using node.data.id (complete node_id like 'node-5')
        const newlyCreatedSessionId = newlyCreatedSession?.nodeId === node.data.id
          ? newlyCreatedSession.sessionId
          : undefined

        if (newlyCreatedSessionId) {
          console.log("[InfiniteCanvas] ✅ Found matching node! Injecting newlyCreatedSessionId for node:", node.data.id, newlyCreatedSessionId)
        }

        return {
          ...node,
          data: {
            ...node.data,
            onEdit: () => handleNodeEdit(node.id),
            onDelete: () => handleNodeDelete(node.id),
            onCreateSession: (nodeId: string) => handleCreateSession(nodeId),
            newlyCreatedSessionId,
            onSessionSelected: () => setNewlyCreatedSession(null),
          },
        }
      })
    )
  }, [nodeManagement.nodes.length, newlyCreatedSession]) // Re-run when nodes count changes or newlyCreatedSession changes

  // ReactFlow event handlers
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => nodeManagement.setNodes((nds) => applyNodeChanges(changes, nds)),
    [nodeManagement.setNodes]
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => nodeManagement.setEdges((eds) => applyEdgeChanges(changes, eds)),
    [nodeManagement.setEdges]
  )

  // Track highest z-index for bringing nodes to front
  const [highestZIndex, setHighestZIndex] = useState(1000)

  // Helper function to bring node to front
  const bringNodeToFront = useCallback(
    (nodeId: string) => {
      const newZIndex = highestZIndex + 1
      setHighestZIndex(newZIndex)

      nodeManagement.setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, style: { ...n.style, zIndex: newZIndex } }
            : n
        )
      )
    },
    [nodeManagement.setNodes, highestZIndex]
  )

  // Bring clicked node to front using z-index
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      bringNodeToFront(node.id)
    },
    [bringNodeToFront]
  )

  // Bring dragged node to front when drag starts
  const onNodeDragStart = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      bringNodeToFront(node.id)
    },
    [bringNodeToFront]
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      // Drag-and-drop connections disabled, using right-click menu instead
      // Keeping this handler for potential future use
    },
    []
  )

  // Handle connection creation from menu
  const handleCreateConnectionFromMenu = () => {
    setCreateConnectionOpen(true)
  }

  // Handle unified connection creation
  const handleCreateConnection = async (
    sourceNodeId: string,
    targetNodeId: string,
    sessionAlignment: string,
    description: string
  ) => {
    if (!mosaicManagement.currentMosaicId) return

    try {
      // TODO: Call API to create connection
      // await apiClient.createConnection(mosaicManagement.currentMosaicId, {
      //   source_node_id: sourceNodeId,
      //   target_node_id: targetNodeId,
      //   session_alignment: sessionAlignment,
      //   description: description || undefined,
      // })

      // For now, just add the edge to the canvas
      nodeManagement.setEdges((eds) =>
        addEdge(
          {
            source: sourceNodeId,
            target: targetNodeId,
            type: "animated",
          },
          eds
        )
      )

      setCreateConnectionOpen(false)
    } catch (error) {
      console.error("Failed to create connection:", error)
    }
  }

  // Handle subscription panel open
  const handleViewSubscriptions = (connectionId: number, source: string, target: string) => {
    setSelectedConnectionId(connectionId)
    setSelectedConnectionNodes({ source, target })
    setSubscriptionPanelOpen(true)
  }

  // Handle node edit
  const handleNodeEdit = (nodeId: string) => {
    // Find the node data from apiNodes
    const nodeData = nodeManagement.apiNodes.find(n => n.node_id === nodeId)
    const flowNode = nodeManagement.nodes.find(n => n.id === nodeId)

    if (nodeData && flowNode) {
      setSelectedNodeForAction({
        id: nodeData.node_id,
        name: flowNode.data.type,
        description: nodeData.description,
        config: nodeData.config,
        autoStart: nodeData.auto_start,
      })
      setEditNodeDialogOpen(true)
    }
  }

  // Handle node delete
  const handleNodeDelete = (nodeId: string) => {
    // Find the node data
    const flowNode = nodeManagement.nodes.find(n => n.id === nodeId)

    if (flowNode) {
      setSelectedNodeForAction({
        id: nodeId,
        name: flowNode.data.type,
        activeSessions: flowNode.data.sessions || 0,
        incomingConnections: flowNode.data.incomingConnections || 0,
        outgoingConnections: flowNode.data.outgoingConnections || 0,
      })
      setDeleteNodeDialogOpen(true)
    }
  }

  // Handle create session
  const handleCreateSession = (nodeId: string) => {
    setSelectedNodeForSession(nodeId)
    setCreateSessionDialogOpen(true)
  }

  // Handle session creation from dialog
  const handleSessionCreate = async (sessionData: { mode: string; model: string }) => {
    if (!selectedNodeForSession || !mosaicManagement.currentMosaicId) return

    try {
      console.log("[InfiniteCanvas] Creating session:", {
        mosaicId: mosaicManagement.currentMosaicId,
        nodeId: selectedNodeForSession,
        ...sessionData
      })

      // Call API to create session
      const newSession = await apiClient.createSession(
        mosaicManagement.currentMosaicId,
        selectedNodeForSession,
        {
          mode: sessionData.mode,
          model: sessionData.model,
        }
      )

      console.log("[InfiniteCanvas] Session created successfully:", newSession.session_id)
      console.log("[InfiniteCanvas] Waiting for session_started notification...")

      // Wait for session_started notification from WebSocket
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          unsubscribe()
          reject(new Error("Timeout waiting for session_started notification"))
        }, 30000) // 30 second timeout

        const unsubscribe = subscribe('*', (message) => {
          // Check if it's an error message
          if ("type" in message && message.type === "error") {
            return
          }

          const wsMessage = message as import("@/contexts/websocket-context").WSMessage

          // Only handle notification messages
          if (wsMessage.role !== "notification") {
            return
          }

          // Check if this is the session_started notification for our new session
          if (wsMessage.message_type === "session_started") {
            const payload = wsMessage.payload as any
            if (payload?.session_id === newSession.session_id) {
              console.log("[InfiniteCanvas] Received session_started notification for:", newSession.session_id)
              clearTimeout(timeout)
              unsubscribe()
              resolve()
            }
          }
        })
      })

      console.log("[InfiniteCanvas] Session started, proceeding with UI updates")

      // Ensure node is expanded so ExpandedNodeCard can handle the auto-selection
      // Find node by complete node_id (e.g., 'node-5')
      const targetNode = nodeManagement.nodes.find(n => n.data.id === selectedNodeForSession)
      if (targetNode && !targetNode.data.expanded) {
        console.log("[InfiniteCanvas] Expanding node to show session list")
        // toggleNodeExpansion uses ReactFlow ID (e.g., '5')
        nodeManagement.toggleNodeExpansion(targetNode.id)

        // Wait for node expansion to complete and state to update
        await new Promise(resolve => setTimeout(resolve, 200))
      }

      // Set flag to trigger ExpandedNodeCard to refresh its session list
      setNewlyCreatedSession({
        nodeId: selectedNodeForSession,
        sessionId: newSession.session_id,
      })

      console.log("[InfiniteCanvas] Signaling ExpandedNodeCard to refresh and select session")

      // Note: Dialog will be closed by CreateSessionDialog's onClose callback
      // ExpandedNodeCard will refresh its session list and auto-select the new session
    } catch (error) {
      console.error("[InfiniteCanvas] Failed to create session:", error)
      // Re-throw error so CreateSessionDialog can handle it
      throw error
    }
  }

  // Confirm edit node
  const handleConfirmEdit = async (data: {
    description?: string | null
    config?: Record<string, any> | null
    auto_start?: boolean | null
  }) => {
    if (!selectedNodeForAction) return
    await nodeManagement.handleEditNode(selectedNodeForAction.id, data)
  }

  // Confirm delete node
  const handleConfirmDelete = async () => {
    if (!selectedNodeForAction) return
    await nodeManagement.handleDeleteNode(selectedNodeForAction.id)
  }

  // Loading state
  if (mosaicManagement.loadingMosaics) {
    return <LoadingScreen />
  }

  return (
    <div className="relative h-screen w-full overflow-hidden">
      {/* Theme-aware canvas background */}
      <CanvasBackground />

      {/* Mosaic Sidebar */}
      <MosaicSidebar
        mosaics={mosaicManagement.mosaics}
        currentMosaicId={mosaicManagement.currentMosaicId}
        onSwitch={mosaicManagement.handleSwitchMosaic}
        onCreateNew={() => mosaicManagement.setCreateMosaicOpen(true)}
        onEdit={(mosaic) => mosaicManagement.setEditingMosaic(mosaic)}
        onDelete={mosaicManagement.handleDeleteMosaic}
        onToggleStatus={mosaicManagement.handleToggleMosaicStatus}
      />

      {/* Main Canvas Area - with left margin for sidebar */}
      <div className="ml-16 h-full">
        <CanvasContextMenu
          onCreateNode={() => canvasState.setCreateNodeOpen(true)}
          onCreateConnection={handleCreateConnectionFromMenu}
          showTopology={canvasState.showTopology}
          onToggleTopology={canvasState.toggleTopology}
        >
          <ReactFlow
            nodes={nodeManagement.nodes}
            edges={nodeManagement.edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onNodeDragStart={onNodeDragStart}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            elevateNodesOnSelect={false}
            fitView
            className="[&_.react-flow\_\_renderer]:!bg-transparent"
            minZoom={0.2}
            maxZoom={1.5}
            zoomOnScroll={false}
            zoomActivationKeyCode="Control"
            zoomOnPinch={true}
            panOnScroll={false}
            panOnDrag={true}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              style={{
                // @ts-ignore - CSS variable is dynamically injected
                color: 'var(--color-background-dots)',
              }}
              className="opacity-50"
            />

            <TopRightActions
              onCreateNode={() => canvasState.setCreateNodeOpen(true)}
              onOpenCommand={() => canvasState.setCommandOpen(true)}
            />

            <AnimatePresence>
              {canvasState.showTopology && <TopologyLegend show={canvasState.showTopology} />}
            </AnimatePresence>
          </ReactFlow>
        </CanvasContextMenu>

        {/* Create Node Floating Card */}
        <AnimatePresence>
          {canvasState.createNodeOpen && (
            <>
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => canvasState.setCreateNodeOpen(false)}
                className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
              />

              {/* Create Node Card */}
              <div className="fixed left-1/2 top-1/2 z-[101] -translate-x-1/2 -translate-y-1/2">
                <CreateNodeCard
                  onClose={() => canvasState.setCreateNodeOpen(false)}
                  onCreate={nodeManagement.handleCreateNode}
                />
              </div>
            </>
          )}
        </AnimatePresence>

        <CommandPalette
          open={canvasState.commandOpen}
          onClose={() => canvasState.setCommandOpen(false)}
        />
        <ConnectionsSidebar
          open={canvasState.connectionsSidebarOpen}
          onClose={() => canvasState.setConnectionsSidebarOpen(false)}
          connections={mockConnections}
          nodes={nodeManagement.nodes}
        />

        {/* Create Connection Dialog */}
        <AnimatePresence>
          {createConnectionOpen && (
            <CreateConnectionDialog
              availableNodes={nodeManagement.nodes}
              onConfirm={handleCreateConnection}
              onCancel={() => setCreateConnectionOpen(false)}
            />
          )}
        </AnimatePresence>

        {/* Subscription Management Panel */}
        <SubscriptionManagementPanel
          open={subscriptionPanelOpen}
          onClose={() => {
            setSubscriptionPanelOpen(false)
            setSelectedConnectionId(null)
            setSelectedConnectionNodes(null)
          }}
          connectionId={selectedConnectionId}
          sourceNodeId={selectedConnectionNodes?.source || ""}
          targetNodeId={selectedConnectionNodes?.target || ""}
          subscriptions={[]}
          onAddSubscription={() => {
            // TODO: Open add subscription dialog
            console.log("Add subscription")
          }}
          onEditSubscription={(subscription) => {
            // TODO: Open edit subscription dialog
            console.log("Edit subscription", subscription)
          }}
          onDeleteSubscription={(subscription) => {
            // TODO: Delete subscription with confirmation
            console.log("Delete subscription", subscription)
          }}
        />
      </div>

      {/* Mosaic Management Dialogs */}
      <MosaicDialog
        open={mosaicManagement.createMosaicOpen}
        onClose={() => mosaicManagement.setCreateMosaicOpen(false)}
        onSubmit={mosaicManagement.handleCreateMosaic}
      />

      <MosaicDialog
        open={!!mosaicManagement.editingMosaic}
        onClose={() => mosaicManagement.setEditingMosaic(null)}
        onSubmit={(name, description) => {
          if (mosaicManagement.editingMosaic) {
            mosaicManagement.handleEditMosaic(mosaicManagement.editingMosaic.id, name, description)
          }
        }}
        mosaic={mosaicManagement.editingMosaic}
      />

      {/* Node Edit Dialog */}
      {selectedNodeForAction && (
        <EditNodeDialog
          open={editNodeDialogOpen}
          onOpenChange={setEditNodeDialogOpen}
          nodeId={selectedNodeForAction.id}
          nodeName={selectedNodeForAction.name}
          initialDescription={selectedNodeForAction.description}
          initialConfig={selectedNodeForAction.config}
          initialAutoStart={selectedNodeForAction.autoStart}
          onSave={handleConfirmEdit}
        />
      )}

      {/* Node Delete Dialog */}
      {selectedNodeForAction && (
        <DeleteNodeDialog
          open={deleteNodeDialogOpen}
          onOpenChange={setDeleteNodeDialogOpen}
          nodeId={selectedNodeForAction.id}
          nodeName={selectedNodeForAction.name}
          activeSessions={selectedNodeForAction.activeSessions}
          incomingConnections={selectedNodeForAction.incomingConnections}
          outgoingConnections={selectedNodeForAction.outgoingConnections}
          onConfirm={handleConfirmDelete}
        />
      )}

      {/* Create Session Dialog */}
      <AnimatePresence>
        {createSessionDialogOpen && selectedNodeForSession && (
          <>
            {/* Background overlay */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={() => setCreateSessionDialogOpen(false)}
            />
            {/* Dialog */}
            <div className="fixed inset-0 flex items-center justify-center z-50 pointer-events-none">
              <div className="pointer-events-auto">
                <CreateSessionDialog
                  nodeId={selectedNodeForSession}
                  onClose={() => {
                    setCreateSessionDialogOpen(false)
                    setSelectedNodeForSession(null)
                  }}
                  onCreate={handleSessionCreate}
                />
              </div>
            </div>
          </>
        )}
      </AnimatePresence>

      {/* Ambient particles effect */}
      <AmbientParticles />
    </div>
  )
}
