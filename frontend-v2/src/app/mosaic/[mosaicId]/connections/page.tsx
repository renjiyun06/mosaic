"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
import { Plus, Trash2, Loader2, Edit, ArrowRight, Link2, AlertCircle } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { SessionAlignment, type NodeOut, type ConnectionOut } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// Session alignment display configuration
const SESSION_ALIGNMENT_CONFIG: Record<SessionAlignment, { label: string; description: string }> = {
  [SessionAlignment.MIRRORING]: {
    label: "镜像模式",
    description: "目标节点会话与源节点会话一一对应，同步创建和关闭"
  },
  [SessionAlignment.TASKING]: {
    label: "任务模式",
    description: "目标节点为每个事件独立创建新会话，适用于任务分发场景"
  },
  [SessionAlignment.AGENT_DRIVEN]: {
    label: "智能体驱动模式",
    description: "由智能体主动调用 task_complete 工具决定会话何时关闭，支持递归任务处理"
  }
}

export default function ConnectionsPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string

  const [connections, setConnections] = useState<ConnectionOut[]>([])
  const [nodes, setNodes] = useState<NodeOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Mobile detection
  const [isMobile, setIsMobile] = useState(false)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formData, setFormData] = useState({
    source_node_id: "",
    target_node_id: "",
    session_alignment: SessionAlignment.TASKING,
    description: "",
  })

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingConnection, setEditingConnection] = useState<ConnectionOut | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editFormData, setEditFormData] = useState({
    session_alignment: SessionAlignment.TASKING,
    description: "",
  })

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingConnection, setDeletingConnection] = useState<ConnectionOut | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Mobile detection effect
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Fetch connections and nodes
  useEffect(() => {
    if (!token) return

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const [connectionsData, nodesData] = await Promise.all([
          apiClient.listConnections(Number(mosaicId)),
          apiClient.listNodes(Number(mosaicId)),
        ])
        setConnections(connectionsData)
        setNodes(nodesData)
      } catch (err) {
        console.error("Failed to fetch data:", err)
        setError(err instanceof Error ? err.message : "Failed to load data")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [mosaicId, token])

  const handleCreateConnection = async () => {
    if (!token) return
    if (!formData.source_node_id || !formData.target_node_id) return

    try {
      setCreating(true)
      const requestData = {
        source_node_id: formData.source_node_id,
        target_node_id: formData.target_node_id,
        session_alignment: formData.session_alignment,
        description: formData.description || undefined,
      }
      await apiClient.createConnection(Number(mosaicId), requestData)

      // Reset form and close dialog
      setFormData({
        source_node_id: "",
        target_node_id: "",
        session_alignment: SessionAlignment.TASKING,
        description: "",
      })
      setCreateDialogOpen(false)

      // Refresh connection list
      const data = await apiClient.listConnections(Number(mosaicId))
      setConnections(data)
    } catch (error) {
      console.error("Failed to create connection:", error)
    } finally {
      setCreating(false)
    }
  }

  const openEditDialog = (connection: ConnectionOut) => {
    setEditingConnection(connection)
    setEditFormData({
      session_alignment: connection.session_alignment,
      description: connection.description || "",
    })
    setEditDialogOpen(true)
  }

  const handleUpdateConnection = async () => {
    if (!token || !editingConnection) return

    try {
      setUpdating(true)
      const requestData = {
        session_alignment: editFormData.session_alignment,
        description: editFormData.description || undefined,
      }
      await apiClient.updateConnection(
        Number(mosaicId),
        editingConnection.id,
        requestData
      )

      // Close dialog
      setEditDialogOpen(false)
      setEditingConnection(null)

      // Refresh connection list
      const data = await apiClient.listConnections(Number(mosaicId))
      setConnections(data)
    } catch (error) {
      console.error("Failed to update connection:", error)
    } finally {
      setUpdating(false)
    }
  }

  const openDeleteDialog = (connection: ConnectionOut) => {
    setDeletingConnection(connection)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConnection = async () => {
    if (!token || !deletingConnection) return

    try {
      setDeleting(true)
      await apiClient.deleteConnection(Number(mosaicId), deletingConnection.id)

      setDeleteDialogOpen(false)
      setDeletingConnection(null)

      // Refresh connection list
      const data = await apiClient.listConnections(Number(mosaicId))
      setConnections(data)
    } catch (error) {
      console.error("Failed to delete connection:", error)
    } finally {
      setDeleting(false)
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
            <h1 className="text-xl sm:text-2xl md:text-3xl font-bold">节点连接</h1>
            <p className="text-muted-foreground mt-1 text-sm md:text-base">管理节点之间的连接关系</p>
          </div>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            disabled={nodes.length < 1}
            className="w-full md:w-auto"
          >
            <Plus className="mr-2 h-4 w-4" />
            新建连接
          </Button>
        </div>
      </div>

      {connections.length === 0 ? (
        nodes.length < 1 ? (
          <div className="flex-1 flex flex-col items-center justify-center pt-8 sm:pt-16 border rounded-lg px-4">
            <AlertCircle className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mb-3 sm:mb-4" />
            <h2 className="text-lg sm:text-xl font-semibold mb-2 text-center">至少需要 1 个节点才能创建连接</h2>
            <p className="text-muted-foreground text-center mb-4 sm:mb-6 max-w-lg text-sm sm:text-base">
              连接用于定义节点之间的通信关系。
              请先在节点管理页面创建至少一个节点。节点可以连接到自己（自环连接）或连接到其他节点。
            </p>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center pt-8 sm:pt-16 border rounded-lg px-4">
            <Link2 className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mb-3 sm:mb-4" />
            <h2 className="text-lg sm:text-xl font-semibold mb-2 text-center">还没有创建任何连接</h2>
            <p className="text-muted-foreground text-center mb-4 sm:mb-6 max-w-lg text-sm sm:text-base">
              连接定义了节点之间的事件流向和会话管理策略。
              创建第一个连接来建立节点间的通信。
            </p>
            <Button onClick={() => setCreateDialogOpen(true)} className="w-full sm:w-auto">
              <Plus className="mr-2 h-4 w-4" />
              创建第一个连接
            </Button>
          </div>
        )
      ) : isMobile ? (
        // Mobile card view
        <div className="flex-1 overflow-auto space-y-3">
          {connections.map((connection) => (
            <Card key={connection.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base font-mono truncate flex-1">
                    {connection.source_node_id}
                  </CardTitle>
                  <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                  <CardTitle className="text-base font-mono truncate flex-1">
                    {connection.target_node_id}
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">会话对齐：</span>
                    <Badge variant="outline" className="text-xs">
                      {SESSION_ALIGNMENT_CONFIG[connection.session_alignment].label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {SESSION_ALIGNMENT_CONFIG[connection.session_alignment].description}
                  </p>
                </div>
                {connection.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {connection.description}
                  </p>
                )}
                <div className="text-xs text-muted-foreground">
                  创建于 {new Date(connection.created_at).toLocaleString("zh-CN", {
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false
                  })}
                </div>
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEditDialog(connection)}
                    className="flex-1"
                  >
                    <Edit className="mr-1.5 h-3.5 w-3.5" />
                    编辑
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openDeleteDialog(connection)}
                    className="text-destructive hover:text-destructive flex-1"
                  >
                    <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        // Desktop table view
        <div className="flex-1 flex flex-col min-h-0 border rounded-lg">
          <div className="flex-1 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-center">源节点</TableHead>
                  <TableHead className="text-center">目标节点</TableHead>
                  <TableHead className="text-center">会话对齐</TableHead>
                  <TableHead className="text-center">描述</TableHead>
                  <TableHead className="text-center">创建时间</TableHead>
                  <TableHead className="text-center w-[120px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {connections.map((connection) => (
                  <TableRow key={connection.id}>
                    <TableCell className="text-center">
                      <div className="font-mono font-medium">
                        {connection.source_node_id}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="font-mono font-medium">
                        {connection.target_node_id}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">
                        {SESSION_ALIGNMENT_CONFIG[connection.session_alignment].label}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center max-w-xs truncate text-sm text-muted-foreground">
                      {connection.description || "—"}
                    </TableCell>
                    <TableCell className="text-center text-sm text-muted-foreground">
                      {new Date(connection.created_at).toLocaleString("zh-CN", {
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
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEditDialog(connection)}
                          title="编辑连接"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openDeleteDialog(connection)}
                          title="删除连接"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Create Connection Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">创建新连接</DialogTitle>
            <DialogDescription className="text-sm">
              在节点之间创建连接关系（支持自环连接）
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="source_node_id" className="text-sm">源节点 *</Label>
              <Select
                value={formData.source_node_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, source_node_id: value })
                }
              >
                <SelectTrigger id="source_node_id" className="text-base">
                  <SelectValue placeholder="选择源节点" />
                </SelectTrigger>
                <SelectContent>
                  {nodes.map((node) => (
                    <SelectItem key={node.node_id} value={node.node_id} className="text-base">
                      {node.node_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                连接的起点，事件从这个节点发出
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="target_node_id" className="text-sm">目标节点 *</Label>
              <Select
                value={formData.target_node_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, target_node_id: value })
                }
              >
                <SelectTrigger id="target_node_id" className="text-base">
                  <SelectValue placeholder="选择目标节点" />
                </SelectTrigger>
                <SelectContent>
                  {nodes.map((node) => (
                    <SelectItem key={node.node_id} value={node.node_id} className="text-base">
                      {node.node_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                连接的终点，事件将发送到这个节点（可以与源节点相同）
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="session_alignment" className="text-sm">会话对齐策略 *</Label>
              <Select
                value={formData.session_alignment}
                onValueChange={(value) =>
                  setFormData({ ...formData, session_alignment: value as SessionAlignment })
                }
              >
                <SelectTrigger id="session_alignment" className="text-base">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SESSION_ALIGNMENT_CONFIG).map(([value, config]) => (
                    <SelectItem key={value} value={value} className="text-base">
                      {config.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {SESSION_ALIGNMENT_CONFIG[formData.session_alignment].description}
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description" className="text-sm">描述（可选）</Label>
              <Textarea
                id="description"
                placeholder="描述这个连接的用途..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                maxLength={500}
                rows={3}
                className="text-base resize-none"
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
              onClick={handleCreateConnection}
              disabled={creating || !formData.source_node_id || !formData.target_node_id}
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

      {/* Edit Connection Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">编辑连接</DialogTitle>
            <DialogDescription className="text-sm">
              更新连接的配置信息
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label className="text-sm">源节点 → 目标节点</Label>
              <div className="flex items-center gap-2 p-3 bg-muted rounded-md">
                <span className="font-medium font-mono text-sm truncate flex-1">
                  {editingConnection?.source_node_id || ""}
                </span>
                <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="font-medium font-mono text-sm truncate flex-1">
                  {editingConnection?.target_node_id || ""}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                连接的源节点和目标节点创建后不可修改
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_session_alignment" className="text-sm">会话对齐策略 *</Label>
              <Select
                value={editFormData.session_alignment}
                onValueChange={(value) =>
                  setEditFormData({ ...editFormData, session_alignment: value as SessionAlignment })
                }
              >
                <SelectTrigger id="edit_session_alignment" className="text-base">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SESSION_ALIGNMENT_CONFIG).map(([value, config]) => (
                    <SelectItem key={value} value={value} className="text-base">
                      {config.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {SESSION_ALIGNMENT_CONFIG[editFormData.session_alignment].description}
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_description" className="text-sm">描述（可选）</Label>
              <Textarea
                id="edit_description"
                placeholder="描述这个连接的用途..."
                value={editFormData.description}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, description: e.target.value })
                }
                maxLength={500}
                rows={3}
                className="text-base resize-none"
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
            <Button onClick={handleUpdateConnection} disabled={updating} className="w-full sm:w-auto">
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
        <DialogContent className="sm:max-w-[500px] max-w-[calc(100vw-2rem)]">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">确认删除连接？</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-4">
            <p className="text-sm text-muted-foreground break-words">
              确定要删除从{" "}
              <span className="font-semibold text-foreground font-mono">
                {deletingConnection?.source_node_id}
              </span>{" "}
              到{" "}
              <span className="font-semibold text-foreground font-mono">
                {deletingConnection?.target_node_id}
              </span>{" "}
              的连接吗？
            </p>
            <p className="text-sm text-amber-600 font-medium">
              ⚠️ 警告：删除连接前必须先删除该连接上的所有订阅。
            </p>
            <p className="text-sm text-muted-foreground">此操作不可撤销。</p>
          </div>
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
              onClick={handleDeleteConnection}
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
    </div>
  )
}
