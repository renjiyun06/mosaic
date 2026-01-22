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
  edgeTypes,
} from "../nodes"
import {
  TopologyLegend,
  CanvasContextMenu,
  TopRightActions,
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

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onOpenCommand: () => canvasState.setCommandOpen(true),
    onCloseCommand: () => canvasState.setCommandOpen(false),
  })

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

  // ReactFlow event handlers
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => nodeManagement.setNodes((nds) => applyNodeChanges(changes, nds)),
    [nodeManagement.setNodes]
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => nodeManagement.setEdges((eds) => applyEdgeChanges(changes, eds)),
    [nodeManagement.setEdges]
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

  // Loading state
  if (mosaicManagement.loadingMosaics) {
    return <LoadingScreen />
  }

  return (
    <div className="relative h-screen w-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
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
      <div className="ml-20 h-full">
        <CanvasContextMenu
          onCreateNode={() => canvasState.setCreateNodeOpen(true)}
          onCreateConnection={handleCreateConnectionFromMenu}
          onShowConnections={() => canvasState.setConnectionsSidebarOpen(true)}
          showTopology={canvasState.showTopology}
          onToggleTopology={canvasState.toggleTopology}
        >
          <ReactFlow
            nodes={nodeManagement.nodes}
            edges={nodeManagement.edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            className="bg-slate-950"
            minZoom={0.2}
            maxZoom={1.5}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="#1e293b"
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

      {/* Ambient particles effect */}
      <AmbientParticles />
    </div>
  )
}
