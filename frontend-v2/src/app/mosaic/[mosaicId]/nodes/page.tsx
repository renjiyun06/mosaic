"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Plus, Trash2, Loader2, Edit, Box, Play, Square, Circle } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { NodeType, NodeStatus, type NodeOut } from "@/lib/types"
import { cn } from "@/lib/utils"
import { JsonEditor } from "@/components/ui/json-editor"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// Node type display configuration
const NODE_TYPE_LABELS: Record<NodeType, string> = {
  [NodeType.CLAUDE_CODE]: 'Claude Code',
  [NodeType.SCHEDULER]: 'Scheduler',
  [NodeType.EMAIL]: 'Email'
}

export default function NodesPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string

  const [nodes, setNodes] = useState<NodeOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Mobile detection
  const [isMobile, setIsMobile] = useState(false)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formData, setFormData] = useState({
    node_id: "",
    node_type: NodeType.CLAUDE_CODE,
    description: "",
    config: "{}",
    auto_start: false,
  })

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingNode, setEditingNode] = useState<NodeOut | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editFormData, setEditFormData] = useState({
    description: "",
    config: "{}",
    auto_start: false,
  })

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingNode, setDeletingNode] = useState<NodeOut | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Stop confirmation dialog state
  const [stopDialogOpen, setStopDialogOpen] = useState(false)
  const [stoppingNode, setStoppingNode] = useState<NodeOut | null>(null)
  const [stopping, setStopping] = useState(false)

  // Node operation state (start)
  const [operatingNodeId, setOperatingNodeId] = useState<string | null>(null)

  // Mobile detection effect
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Fetch nodes
  useEffect(() => {
    if (!token) return

    const fetchNodes = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await apiClient.listNodes(Number(mosaicId))
        setNodes(data)
      } catch (err) {
        console.error("Failed to fetch nodes:", err)
        setError(err instanceof Error ? err.message : "Failed to load nodes")
      } finally {
        setLoading(false)
      }
    }

    fetchNodes()
  }, [mosaicId, token])

  // Listen for mosaic status changes and refresh node list
  useEffect(() => {
    const handleMosaicStatusChange = (event: Event) => {
      const customEvent = event as CustomEvent<{ status: string; mosaicId: number }>
      // Only refresh if it's the current mosaic
      if (customEvent.detail.mosaicId === Number(mosaicId)) {
        console.log("[Nodes] Mosaic status changed, refreshing node list...")
        // Refresh node list
        apiClient.listNodes(Number(mosaicId))
          .then(data => setNodes(data))
          .catch(err => console.error("Failed to refresh nodes:", err))
      }
    }

    window.addEventListener('mosaic-status-changed', handleMosaicStatusChange)

    return () => {
      window.removeEventListener('mosaic-status-changed', handleMosaicStatusChange)
    }
  }, [mosaicId])

  const handleCreateNode = async () => {
    if (!token) return
    if (!formData.node_id.trim()) return

    // Parse config JSON
    let config = {}
    if (formData.config.trim()) {
      try {
        config = JSON.parse(formData.config)
      } catch (e) {
        alert("配置必须是有效的 JSON 格式")
        return
      }
    }

    try {
      setCreating(true)
      const requestData = {
        node_id: formData.node_id,
        node_type: formData.node_type,
        description: formData.description || undefined,
        config,
        auto_start: formData.auto_start,
      }
      await apiClient.createNode(Number(mosaicId), requestData)

      // Reset form and close dialog
      setFormData({
        node_id: "",
        node_type: NodeType.CLAUDE_CODE,
        description: "",
        config: "{}",
        auto_start: false,
      })
      setCreateDialogOpen(false)

      // Refresh node list
      const data = await apiClient.listNodes(Number(mosaicId))
      setNodes(data)
    } catch (error) {
      console.error("Failed to create node:", error)
      alert(error instanceof Error ? error.message : "Failed to create node")
    } finally {
      setCreating(false)
    }
  }

  const openEditDialog = (node: NodeOut) => {
    setEditingNode(node)
    setEditFormData({
      description: node.description || "",
      config: JSON.stringify(node.config || {}, null, 2),
      auto_start: node.auto_start,
    })
    setEditDialogOpen(true)
  }

  const handleUpdateNode = async () => {
    if (!token || !editingNode) return

    // Parse config JSON
    let config = {}
    if (editFormData.config.trim()) {
      try {
        config = JSON.parse(editFormData.config)
      } catch (e) {
        alert("配置必须是有效的 JSON 格式")
        return
      }
    }

    try {
      setUpdating(true)
      const requestData = {
        description: editFormData.description || undefined,
        config,
        auto_start: editFormData.auto_start,
      }
      await apiClient.updateNode(
        Number(mosaicId),
        editingNode.node_id,
        requestData
      )

      // Close dialog
      setEditDialogOpen(false)
      setEditingNode(null)

      // Refresh node list
      const data = await apiClient.listNodes(Number(mosaicId))
      setNodes(data)
    } catch (error) {
      console.error("Failed to update node:", error)
      alert(error instanceof Error ? error.message : "Failed to update node")
    } finally {
      setUpdating(false)
    }
  }

  const openDeleteDialog = (node: NodeOut) => {
    setDeletingNode(node)
    setDeleteDialogOpen(true)
  }

  const handleDeleteNode = async () => {
    if (!token || !deletingNode) return

    try {
      setDeleting(true)
      await apiClient.deleteNode(Number(mosaicId), deletingNode.node_id)

      setDeleteDialogOpen(false)
      setDeletingNode(null)

      // Refresh node list
      const data = await apiClient.listNodes(Number(mosaicId))
      setNodes(data)
    } catch (error) {
      console.error("Failed to delete node:", error)
      alert(error instanceof Error ? error.message : "Failed to delete node")
    } finally {
      setDeleting(false)
    }
  }

  const handleStartNode = async (node: NodeOut) => {
    if (!token) return

    try {
      setOperatingNodeId(node.node_id)
      const updatedNode = await apiClient.startNode(Number(mosaicId), node.node_id)

      // Update the specific node in the list with the returned status
      setNodes(nodes.map(n => n.id === updatedNode.id ? updatedNode : n))
    } catch (error) {
      console.error("Failed to start node:", error)
      alert(error instanceof Error ? error.message : "Failed to start node")
    } finally {
      setOperatingNodeId(null)
    }
  }

  const openStopDialog = (node: NodeOut) => {
    setStoppingNode(node)
    setStopDialogOpen(true)
  }

  const handleStopNode = async () => {
    if (!token || !stoppingNode) return

    try {
      setStopping(true)
      const updatedNode = await apiClient.stopNode(Number(mosaicId), stoppingNode.node_id)

      // Update the specific node in the list with the returned status
      setNodes(nodes.map(n => n.id === updatedNode.id ? updatedNode : n))
      setStopDialogOpen(false)
      setStoppingNode(null)
    } catch (error) {
      console.error("Failed to stop node:", error)
      alert(error instanceof Error ? error.message : "Failed to stop node")
    } finally {
      setStopping(false)
    }
  }

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
    <div className="flex flex-col h-full space-y-3 sm:space-y-4 md:space-y-6 overflow-auto">
      <div className="flex-shrink-0">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-bold">节点管理</h1>
            <p className="text-muted-foreground mt-1 text-sm md:text-base">管理 Mosaic 实例中的节点</p>
          </div>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            className="w-full md:w-auto"
          >
            <Plus className="mr-2 h-4 w-4" />
            新建节点
          </Button>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center pt-8 sm:pt-16 border rounded-lg px-4">
          <Box className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mb-3 sm:mb-4" />
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-center">还没有创建任何节点</h2>
          <p className="text-muted-foreground text-center mb-4 sm:mb-6 max-w-lg text-sm sm:text-base">
            节点是 Mosaic 系统的核心组件，用于处理事件和执行任务。
            创建第一个节点来开始构建你的事件网络。
          </p>
          <Button onClick={() => setCreateDialogOpen(true)} className="w-full sm:w-auto">
            <Plus className="mr-2 h-4 w-4" />
            创建第一个节点
          </Button>
        </div>
      ) : isMobile ? (
        // Mobile card view
        <div className="flex-1 overflow-auto space-y-3">
          {nodes.map((node) => {
            const isOperating = operatingNodeId === node.node_id
            const isRunning = node.status === NodeStatus.RUNNING

            return (
              <Card key={node.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Box className="h-4 w-4 text-blue-500 shrink-0" />
                      <CardTitle className="text-base font-mono truncate">{node.node_id}</CardTitle>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {isRunning ? (
                        <Badge className="bg-green-500 hover:bg-green-600 text-xs">
                          <Circle className="mr-1 h-2 w-2 fill-current" />
                          运行中
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs">
                          <Circle className="mr-1 h-2 w-2 fill-current" />
                          停止
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">类型：</span>
                      <Badge variant="outline" className="ml-1 text-xs">
                        {NODE_TYPE_LABELS[node.node_type]}
                      </Badge>
                    </div>
                    <div>
                      <span className="text-muted-foreground">会话：</span>
                      <Badge variant="outline" className="ml-1 text-xs">{node.active_session_count}</Badge>
                    </div>
                    <div>
                      <span className="text-muted-foreground">自动启动：</span>
                      <Badge variant={node.auto_start ? "default" : "secondary"} className="ml-1 text-xs">
                        {node.auto_start ? "是" : "否"}
                      </Badge>
                    </div>
                  </div>
                  {node.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {node.description}
                    </p>
                  )}
                  <div className="text-xs text-muted-foreground">
                    创建于 {new Date(node.created_at).toLocaleString("zh-CN", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false
                    })}
                  </div>
                  <div className="flex gap-2 pt-2">
                    {isRunning ? (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => openStopDialog(node)}
                        disabled={isOperating}
                        className="flex-1"
                      >
                        <Square className="mr-1.5 h-3.5 w-3.5" />
                        停止
                      </Button>
                    ) : (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => handleStartNode(node)}
                        disabled={isOperating}
                        className="flex-1"
                      >
                        {isOperating ? (
                          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        启动
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEditDialog(node)}
                      className="flex-1"
                    >
                      <Edit className="mr-1.5 h-3.5 w-3.5" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openDeleteDialog(node)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : (
        // Desktop table view
        <div className="flex-1 flex flex-col min-h-0 border rounded-lg">
          <div className="flex-1 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-center">节点 ID</TableHead>
                  <TableHead className="text-center">类型</TableHead>
                  <TableHead className="text-center">状态</TableHead>
                  <TableHead className="text-center">活跃会话</TableHead>
                  <TableHead className="text-center">自动启动</TableHead>
                  <TableHead className="text-center">描述</TableHead>
                  <TableHead className="text-center">创建时间</TableHead>
                  <TableHead className="text-center w-[180px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {nodes.map((node) => {
                  const isOperating = operatingNodeId === node.node_id
                  const isRunning = node.status === NodeStatus.RUNNING

                  return (
                    <TableRow key={node.id}>
                      <TableCell className="text-center">
                        <div className="flex items-center gap-2 justify-center">
                          <Box className="h-4 w-4 text-blue-500" />
                          <span className="font-medium font-mono">{node.node_id}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">
                          {NODE_TYPE_LABELS[node.node_type]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        {isRunning ? (
                          <Badge className="bg-green-500 hover:bg-green-600">
                            <Circle className="mr-1 h-2 w-2 fill-current" />
                            运行中
                          </Badge>
                        ) : (
                          <Badge variant="secondary">
                            <Circle className="mr-1 h-2 w-2 fill-current" />
                            已停止
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{node.active_session_count}</Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={node.auto_start ? "default" : "secondary"}>
                          {node.auto_start ? "是" : "否"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center max-w-xs truncate text-sm text-muted-foreground">
                        {node.description || "—"}
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {new Date(node.created_at).toLocaleString("zh-CN", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: false
                        })}
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex gap-1 justify-center">
                          {isRunning ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => openStopDialog(node)}
                              disabled={isOperating}
                              title="停止节点"
                            >
                              <Square className="h-4 w-4 text-red-600" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleStartNode(node)}
                              disabled={isOperating}
                              title="启动节点"
                            >
                              {isOperating ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Play className="h-4 w-4 text-green-600" />
                              )}
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditDialog(node)}
                            title="编辑节点"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openDeleteDialog(node)}
                            title="删除节点"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Create Node Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">创建新节点</DialogTitle>
            <DialogDescription className="text-sm">
              为当前 Mosaic 实例创建一个新的节点
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="node_id" className="text-sm">节点 ID *</Label>
              <Input
                id="node_id"
                placeholder="例如：scheduler_1, email_main"
                value={formData.node_id}
                onChange={(e) =>
                  setFormData({ ...formData, node_id: e.target.value })
                }
                maxLength={100}
                className="text-base"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="node_type" className="text-sm">节点类型 *</Label>
              <Select
                value={formData.node_type}
                onValueChange={(value) =>
                  setFormData({ ...formData, node_type: value as NodeType })
                }
              >
                <SelectTrigger id="node_type" className="text-base">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(NODE_TYPE_LABELS).map(([type, label]) => (
                    <SelectItem key={type} value={type} className="text-base">
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description" className="text-sm">描述（可选）</Label>
              <Textarea
                id="description"
                placeholder="描述这个节点的用途..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                maxLength={1000}
                rows={3}
                className="text-base resize-none"
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="auto_start"
                  checked={formData.auto_start}
                  onChange={(e) =>
                    setFormData({ ...formData, auto_start: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="auto_start" className="text-sm font-normal cursor-pointer">
                  自动启动
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">
                当 Mosaic 启动时自动启动此节点
              </p>
            </div>
            <div>
              <JsonEditor
                value={formData.config}
                onChange={(value) =>
                  setFormData({ ...formData, config: value })
                }
                height="200px"
              />
            </div>
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
              disabled={creating}
              className="w-full sm:w-auto"
            >
              取消
            </Button>
            <Button
              onClick={handleCreateNode}
              disabled={creating || !formData.node_id.trim()}
              className="w-full sm:w-auto"
            >
              {creating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  创建中...
                </>
              ) : (
                "创建"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Node Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">编辑节点</DialogTitle>
            <DialogDescription className="text-sm break-words">
              更新节点 {editingNode?.node_id} 的配置信息
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit_node_id" className="text-sm">节点 ID</Label>
              <Input
                id="edit_node_id"
                value={editingNode?.node_id || ""}
                disabled
                className="bg-muted text-base"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_node_type" className="text-sm">节点类型</Label>
              <Input
                id="edit_node_type"
                value={editingNode ? NODE_TYPE_LABELS[editingNode.node_type] : ""}
                disabled
                className="bg-muted text-base"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_description" className="text-sm">描述（可选）</Label>
              <Textarea
                id="edit_description"
                placeholder="描述这个节点的用途..."
                value={editFormData.description}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, description: e.target.value })
                }
                maxLength={1000}
                rows={3}
                className="text-base resize-none"
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit_auto_start"
                  checked={editFormData.auto_start}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, auto_start: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="edit_auto_start" className="text-sm font-normal cursor-pointer">
                  自动启动
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">
                当 Mosaic 启动时自动启动此节点
              </p>
            </div>
            <div>
              <JsonEditor
                value={editFormData.config}
                onChange={(value) =>
                  setEditFormData({ ...editFormData, config: value })
                }
                height="200px"
              />
            </div>
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setEditDialogOpen(false)}
              disabled={updating}
              className="w-full sm:w-auto"
            >
              取消
            </Button>
            <Button onClick={handleUpdateNode} disabled={updating} className="w-full sm:w-auto">
              {updating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  更新中...
                </>
              ) : (
                "保存"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[425px] max-w-[calc(100vw-2rem)]">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">确认删除节点？</DialogTitle>
            <DialogDescription className="text-sm break-words">
              此操作将删除节点 <span className="font-semibold text-foreground">{deletingNode?.node_id}</span>。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleting}
              className="w-full sm:w-auto"
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteNode}
              disabled={deleting}
              className="w-full sm:w-auto"
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  删除中...
                </>
              ) : (
                "确认删除"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Stop Confirmation Dialog */}
      <Dialog open={stopDialogOpen} onOpenChange={setStopDialogOpen}>
        <DialogContent className="sm:max-w-[425px] max-w-[calc(100vw-2rem)]">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">确认停止节点？</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-4">
            <p className="text-sm text-muted-foreground break-words">
              确定要停止节点 <span className="font-semibold text-foreground">{stoppingNode?.node_id}</span> 吗？
            </p>
            <p className="text-sm text-amber-600 font-medium">
              ⚠️ 警告：该节点下的所有活动会话将被无条件关闭。
            </p>
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setStopDialogOpen(false)}
              disabled={stopping}
              className="w-full sm:w-auto"
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleStopNode}
              disabled={stopping}
              className="w-full sm:w-auto"
            >
              {stopping ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  停止中...
                </>
              ) : (
                "确认停止"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
