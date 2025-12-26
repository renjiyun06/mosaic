"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useDialog } from "@/hooks/use-dialog"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Plus, Trash2, Loader2, Edit, Box, Play, Square, RotateCw } from "lucide-react"
import { apiClient, type NodeResponse } from "@/lib/api"
import { useAuthStore, useMosaicStore } from "@/lib/store"
import { NodeType, NODE_TYPE_CONFIG, getAvailableNodeTypes } from "@/lib/enums"
import { JsonEditor } from "@/components/ui/json-editor"
import { EmptyState } from "@/components/ui/empty-state"

export default function NodesPage() {
  const params = useParams()
  const router = useRouter()
  const { token } = useAuthStore()
  const { mosaicStatusChangeTimestamp } = useMosaicStore()
  const { confirm, showError, showSuccess } = useDialog()
  const mosaicId = params.mosaicId as string

  const [nodes, setNodes] = useState<NodeResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
  const [editingNode, setEditingNode] = useState<NodeResponse | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editFormData, setEditFormData] = useState({
    description: "",
    config: "{}",
    auto_start: false,
  })

  // Node operation state (start/stop/restart)
  const [operatingNode, setOperatingNode] = useState<{
    nodeId: string
    operation: "start" | "stop" | "restart"
  } | null>(null)

  // Fetch nodes
  useEffect(() => {
    if (!token) {
      router.push("/login")
      return
    }

    const fetchNodes = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await apiClient.listNodes(Number(mosaicId), token)
        setNodes(data)
      } catch (err) {
        console.error("Failed to fetch nodes:", err)
        setError(err instanceof Error ? err.message : "Failed to load nodes")
      } finally {
        setLoading(false)
      }
    }

    fetchNodes()
  }, [mosaicId, token, router])

  // Auto-refresh nodes when mosaic status changes (e.g., started)
  useEffect(() => {
    if (!token) return

    const timestamp = mosaicStatusChangeTimestamp[mosaicId]
    if (!timestamp) return

    // Refresh immediately (backend waits for auto-start nodes to complete)
    const refreshNodes = async () => {
      try {
        console.log("Auto-refreshing node list after mosaic status change")
        const data = await apiClient.listNodes(Number(mosaicId), token)
        setNodes(data)
      } catch (err) {
        console.error("Failed to auto-refresh nodes:", err)
      }
    }

    refreshNodes()
  }, [mosaicStatusChangeTimestamp, mosaicId, token])

  const handleCreateNode = async () => {
    if (!token) return
    if (!formData.node_id.trim()) return

    // Parse config JSON
    let config = {}
    if (formData.config.trim()) {
      try {
        config = JSON.parse(formData.config)
      } catch (e) {
        showError("配置必须是有效的 JSON 格式", "配置格式错误")
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
      console.log('Creating node with data:', requestData)
      await apiClient.createNode(Number(mosaicId), requestData, token)

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
      const data = await apiClient.listNodes(Number(mosaicId), token)
      setNodes(data)
    } catch (error) {
      console.error("Failed to create node:", error)
      showError(error instanceof Error ? error.message : "Failed to create node", "创建节点失败")
    } finally {
      setCreating(false)
    }
  }

  const openEditDialog = (node: NodeResponse) => {
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
        showError("配置必须是有效的 JSON 格式", "配置格式错误")
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
        requestData,
        token
      )

      // Close dialog
      setEditDialogOpen(false)
      setEditingNode(null)

      // Refresh node list
      const data = await apiClient.listNodes(Number(mosaicId), token)
      setNodes(data)
    } catch (error) {
      console.error("Failed to update node:", error)
      showError(error instanceof Error ? error.message : "Failed to update node", "更新节点失败")
    } finally{
      setUpdating(false)
    }
  }

  const handleDeleteNode = (node: NodeResponse) => {
    confirm({
      title: "确认删除节点？",
      description: `确定要删除节点 ${node.node_id} 吗？此操作不可撤销。`,
      confirmText: "删除",
      variant: "danger",
      onConfirm: async () => {
        if (!token) return
        try {
          await apiClient.deleteNode(Number(mosaicId), node.node_id, token)
          // Refresh node list
          const data = await apiClient.listNodes(Number(mosaicId), token)
          setNodes(data)
        } catch (error) {
          console.error("Failed to delete node:", error)
          showError(error instanceof Error ? error.message : "Failed to delete node", "删除节点失败")
          throw error // Prevent dialog from closing
        }
      }
    })
  }

  const handleStartNode = async (node: NodeResponse) => {
    if (!token) return

    try {
      setOperatingNode({ nodeId: node.node_id, operation: "start" })
      const updatedNode = await apiClient.startNode(Number(mosaicId), node.node_id, token)

      // Update the specific node in the list with the returned status
      setNodes(nodes.map(n => n.id === updatedNode.id ? updatedNode : n))
    } catch (error) {
      console.error("Failed to start node:", error)
      showError(error instanceof Error ? error.message : "Failed to start node", "启动节点失败")
    } finally {
      setOperatingNode(null)
    }
  }

  const handleStopNode = (node: NodeResponse) => {
    confirm({
      title: "确认停止节点？",
      description: (
        <>
          确定要停止节点 <strong>{node.node_id}</strong> 吗？
          <br />
          <br />
          <span className="text-amber-600 font-medium">
            ⚠️ 警告：该节点下的所有活动会话将被无条件关闭。
          </span>
        </>
      ),
      confirmText: "确认停止",
      variant: "danger",
      onConfirm: async () => {
        if (!token) return
        try {
          setOperatingNode({ nodeId: node.node_id, operation: "stop" })
          const updatedNode = await apiClient.stopNode(Number(mosaicId), node.node_id, token)
          // Update the specific node in the list with the returned status
          setNodes(nodes.map(n => n.id === updatedNode.id ? updatedNode : n))
          setOperatingNode(null)
        } catch (error) {
          console.error("Failed to stop node:", error)
          setOperatingNode(null)
          showError(error instanceof Error ? error.message : "Failed to stop node", "停止节点失败")
          throw error // Prevent dialog from closing
        }
      }
    })
  }

  const handleRestartNode = (node: NodeResponse) => {
    confirm({
      title: "确认重启节点？",
      description: (
        <>
          确定要重启节点 <strong>{node.node_id}</strong> 吗？
          <br />
          <br />
          <span className="text-amber-600 font-medium">
            ⚠️ 警告：该节点下的所有活动会话将被关闭，重启后会创建新的会话。
          </span>
        </>
      ),
      confirmText: "确认重启",
      variant: "warning",
      onConfirm: async () => {
        if (!token) return
        try {
          setOperatingNode({ nodeId: node.node_id, operation: "restart" })
          const updatedNode = await apiClient.restartNode(Number(mosaicId), node.node_id, token)
          // Update the specific node in the list with the returned status
          setNodes(nodes.map(n => n.id === updatedNode.id ? updatedNode : n))
          setOperatingNode(null)
        } catch (error) {
          console.error("Failed to restart node:", error)
          setOperatingNode(null)
          showError(error instanceof Error ? error.message : "Failed to restart node", "重启节点失败")
          throw error // Prevent dialog from closing
        }
      }
    })
  }

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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">节点管理</h1>
          <p className="text-muted-foreground mt-1">管理 Mosaic 实例中的节点</p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          新建节点
        </Button>
      </div>

      {nodes.length === 0 ? (
        <EmptyState
          icon={Box}
          title="还没有创建任何节点"
          description="节点是 Mosaic 系统的核心组件，用于处理事件和执行任务。创建第一个节点来开始构建你的事件网络。"
          action={
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              创建第一个节点
            </Button>
          }
        />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-center">节点 ID</TableHead>
                <TableHead className="text-center">类型</TableHead>
                <TableHead className="text-center">状态</TableHead>
                <TableHead className="text-center">自动启动</TableHead>
                <TableHead className="text-center">描述</TableHead>
                <TableHead className="text-center">创建时间</TableHead>
                <TableHead className="text-center w-[200px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nodes.map((node) => {
                const nodeTypeConfig =
                  NODE_TYPE_CONFIG[node.node_type as NodeType] ||
                  NODE_TYPE_CONFIG[NodeType.CLAUDE_CODE]
                const IconComponent = nodeTypeConfig.icon

                const isOperating = operatingNode?.nodeId === node.node_id
                const isRunning = node.status === "running"

                return (
                  <TableRow key={node.id}>
                    <TableCell className="text-center">
                      <div className="flex items-center gap-2 justify-center">
                        <IconComponent
                          className={`h-4 w-4 ${nodeTypeConfig.color}`}
                        />
                        <span className="font-medium font-mono">{node.node_id}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">{nodeTypeConfig.label}</Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {isRunning ? (
                        <Badge className="bg-green-500 text-white">运行中</Badge>
                      ) : (
                        <Badge variant="secondary">已停止</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant={node.auto_start ? "default" : "outline"}>
                        {node.auto_start ? "是" : "否"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center text-sm text-muted-foreground">
                      {node.description || "暂无描述"}
                    </TableCell>
                    <TableCell className="text-center text-sm text-muted-foreground">
                      {new Date(node.created_at).toLocaleString("zh-CN", {
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        hour12: false
                      })}
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex gap-1 justify-center">
                        {isRunning ? (
                          <>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleStopNode(node)}
                              disabled={isOperating}
                              title="停止节点"
                            >
                              {isOperating && operatingNode?.operation === "stop" ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Square className="h-4 w-4 text-red-600" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRestartNode(node)}
                              disabled={isOperating}
                              title="重启节点"
                            >
                              {isOperating && operatingNode?.operation === "restart" ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RotateCw className="h-4 w-4 text-blue-600" />
                              )}
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleStartNode(node)}
                            disabled={isOperating}
                            title="启动节点"
                          >
                            {isOperating && operatingNode?.operation === "start" ? (
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
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteNode(node)}
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
      )}

      {/* Create Node Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>创建新节点</DialogTitle>
            <DialogDescription>
              为当前 Mosaic 实例创建一个新的节点
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="node_id">节点 ID *</Label>
              <Input
                id="node_id"
                placeholder="例如：scheduler_1, email_main"
                value={formData.node_id}
                onChange={(e) =>
                  setFormData({ ...formData, node_id: e.target.value })
                }
                maxLength={100}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="node_type">节点类型 *</Label>
              <select
                id="node_type"
                value={formData.node_type}
                onChange={(e) =>
                  setFormData({ ...formData, node_type: e.target.value as NodeType })
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {getAvailableNodeTypes().map((nodeType) => (
                  <option key={nodeType} value={nodeType}>
                    {NODE_TYPE_CONFIG[nodeType].label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">描述（可选）</Label>
              <Textarea
                id="description"
                placeholder="描述这个节点的用途..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                maxLength={1000}
                rows={3}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="auto_start">自动启动</Label>
                <p className="text-xs text-muted-foreground">
                  当 Mosaic 启动时自动启动此节点
                </p>
              </div>
              <Switch
                id="auto_start"
                checked={formData.auto_start}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, auto_start: checked })
                }
              />
            </div>
            <div>
              <JsonEditor
                value={formData.config}
                onChange={(value) =>
                  setFormData({ ...formData, config: value })
                }
                height="180px"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
              disabled={creating}
            >
              取消
            </Button>
            <Button
              onClick={handleCreateNode}
              disabled={creating || !formData.node_id.trim()}
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
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑节点</DialogTitle>
            <DialogDescription>
              更新节点 {editingNode?.node_id} 的配置信息
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit_node_id">节点 ID</Label>
              <Input
                id="edit_node_id"
                value={editingNode?.node_id || ""}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">节点 ID 创建后不可修改</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_node_type">节点类型</Label>
              <Input
                id="edit_node_type"
                value={editingNode ? NODE_TYPE_CONFIG[editingNode.node_type as NodeType]?.label : ""}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">节点类型创建后不可修改</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_description">描述（可选）</Label>
              <Textarea
                id="edit_description"
                placeholder="描述这个节点的用途..."
                value={editFormData.description}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, description: e.target.value })
                }
                maxLength={1000}
                rows={3}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="edit_auto_start">自动启动</Label>
                <p className="text-xs text-muted-foreground">
                  当 Mosaic 启动时自动启动此节点
                </p>
              </div>
              <Switch
                id="edit_auto_start"
                checked={editFormData.auto_start}
                onCheckedChange={(checked) =>
                  setEditFormData({ ...editFormData, auto_start: checked })
                }
              />
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
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditDialogOpen(false)}
              disabled={updating}
            >
              取消
            </Button>
            <Button onClick={handleUpdateNode} disabled={updating}>
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

    </div>
  )
}
