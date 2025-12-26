"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Plus, Trash2, Loader2, Edit, ArrowRight, Link2, AlertCircle } from "lucide-react"
import { apiClient, type NodeResponse, type ConnectionResponse } from "@/lib/api"
import { useAuthStore } from "@/lib/store"
import {
  SessionAlignment,
  SESSION_ALIGNMENT_CONFIG,
  getSessionAlignmentLabel,
} from "@/lib/enums"
import { EmptyState } from "@/components/ui/empty-state"

export default function ConnectionsPage() {
  const params = useParams()
  const router = useRouter()
  const { token } = useAuthStore()
  const mosaicId = params.mosaicId as string

  const [connections, setConnections] = useState<ConnectionResponse[]>([])
  const [nodes, setNodes] = useState<NodeResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
  const [editingConnection, setEditingConnection] = useState<ConnectionResponse | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editFormData, setEditFormData] = useState({
    session_alignment: SessionAlignment.TASKING,
    description: "",
  })

  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingConnection, setDeletingConnection] = useState<ConnectionResponse | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Fetch connections and nodes
  useEffect(() => {
    if (!token) {
      router.push("/login")
      return
    }

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const [connectionsData, nodesData] = await Promise.all([
          apiClient.listConnections(Number(mosaicId), token),
          apiClient.listNodes(Number(mosaicId), token),
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
  }, [mosaicId, token, router])


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
      await apiClient.createConnection(Number(mosaicId), requestData, token)

      // Reset form and close dialog
      setFormData({
        source_node_id: "",
        target_node_id: "",
        session_alignment: SessionAlignment.TASKING,
        description: "",
      })
      setCreateDialogOpen(false)

      // Refresh connection list
      const data = await apiClient.listConnections(Number(mosaicId), token)
      setConnections(data)
    } catch (error) {
      console.error("Failed to create connection:", error)
      const errorMessage = error instanceof Error ? error.message : "Failed to create connection"
      alert(`创建连接失败：${errorMessage}`)
    } finally {
      setCreating(false)
    }
  }

  const openEditDialog = (connection: ConnectionResponse) => {
    setEditingConnection(connection)
    setEditFormData({
      session_alignment: connection.session_alignment as SessionAlignment,
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
        requestData,
        token
      )

      // Close dialog
      setEditDialogOpen(false)
      setEditingConnection(null)

      // Refresh connection list
      const data = await apiClient.listConnections(Number(mosaicId), token)
      setConnections(data)
    } catch (error) {
      console.error("Failed to update connection:", error)
      alert(error instanceof Error ? error.message : "Failed to update connection")
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteConnection = async () => {
    if (!token || !deletingConnection) return

    try {
      setDeleting(true)
      await apiClient.deleteConnection(
        Number(mosaicId),
        deletingConnection.id,
        token
      )

      // Close dialog
      setDeleteDialogOpen(false)
      setDeletingConnection(null)

      // Refresh connection list
      const data = await apiClient.listConnections(Number(mosaicId), token)
      setConnections(data)
    } catch (error) {
      console.error("Failed to delete connection:", error)
      alert(error instanceof Error ? error.message : "Failed to delete connection")
    } finally {
      setDeleting(false)
    }
  }

  const openDeleteDialog = (connection: ConnectionResponse) => {
    setDeletingConnection(connection)
    setDeleteDialogOpen(true)
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
          <h1 className="text-3xl font-bold">节点连接</h1>
          <p className="text-muted-foreground mt-1">管理节点之间的连接关系</p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} disabled={nodes.length < 2}>
          <Plus className="mr-2 h-4 w-4" />
          新建连接
        </Button>
      </div>

      {connections.length === 0 ? (
        nodes.length < 2 ? (
          <EmptyState
            icon={AlertCircle}
            title="至少需要 2 个节点才能创建连接"
            description="连接用于定义节点之间的通信关系。请先在节点管理页面创建至少两个节点，然后再创建连接。"
          />
        ) : (
          <EmptyState
            icon={Link2}
            title="还没有创建任何连接"
            description="连接定义了节点之间的事件流向和会话管理策略。创建第一个连接来建立节点间的通信。"
            action={
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                创建第一个连接
              </Button>
            }
          />
        )
      ) : (
        <div className="rounded-md border">
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
                      {getSessionAlignmentLabel(
                        connection.session_alignment as SessionAlignment
                      )}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center text-sm text-muted-foreground">
                    {connection.description || "暂无描述"}
                  </TableCell>
                  <TableCell className="text-center text-sm text-muted-foreground">
                    {new Date(connection.created_at).toLocaleString("zh-CN", {
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
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(connection)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openDeleteDialog(connection)}
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
      )}

      {/* Create Connection Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={(open) => {
        setCreateDialogOpen(open)
        if (!open) {
          // Reset form when dialog closes
          setFormData({
            source_node_id: "",
            target_node_id: "",
            session_alignment: SessionAlignment.TASKING,
            description: "",
          })
        }
      }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>创建新连接</DialogTitle>
            <DialogDescription>
              在两个节点之间创建连接关系
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="source_node_id">源节点 *</Label>
              <Select
                value={formData.source_node_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, source_node_id: value })
                }
              >
                <SelectTrigger id="source_node_id">
                  <SelectValue placeholder="选择源节点" />
                </SelectTrigger>
                <SelectContent>
                  {nodes.map((node) => (
                    <SelectItem key={node.node_id} value={node.node_id}>
                      {node.node_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="target_node_id">目标节点 *</Label>
              <Select
                value={formData.target_node_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, target_node_id: value })
                }
              >
                <SelectTrigger id="target_node_id">
                  <SelectValue placeholder="选择目标节点" />
                </SelectTrigger>
                <SelectContent>
                  {nodes.map((node) => (
                    <SelectItem key={node.node_id} value={node.node_id}>
                      {node.node_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="session_alignment">会话对齐策略 *</Label>
              <Select
                value={formData.session_alignment}
                onValueChange={(value) =>
                  setFormData({ ...formData, session_alignment: value as SessionAlignment })
                }
              >
                <SelectTrigger id="session_alignment">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(SessionAlignment).map((alignment) => (
                    <SelectItem key={alignment} value={alignment}>
                      {SESSION_ALIGNMENT_CONFIG[alignment].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {SESSION_ALIGNMENT_CONFIG[formData.session_alignment].description}
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">描述（可选）</Label>
              <Textarea
                id="description"
                placeholder="描述这个连接的用途..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                maxLength={500}
                rows={3}
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
              onClick={handleCreateConnection}
              disabled={creating || !formData.source_node_id || !formData.target_node_id}
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
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑连接</DialogTitle>
            <DialogDescription>
              更新连接的配置信息
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>源节点 → 目标节点</Label>
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium font-mono">
                  {editingConnection ? editingConnection.source_node_id : ""}
                </span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium font-mono">
                  {editingConnection ? editingConnection.target_node_id : ""}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">连接的源节点和目标节点创建后不可修改</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_session_alignment">会话对齐策略 *</Label>
              <Select
                value={editFormData.session_alignment}
                onValueChange={(value) =>
                  setEditFormData({ ...editFormData, session_alignment: value as SessionAlignment })
                }
              >
                <SelectTrigger id="edit_session_alignment">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(SessionAlignment).map((alignment) => (
                    <SelectItem key={alignment} value={alignment}>
                      {SESSION_ALIGNMENT_CONFIG[alignment].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {SESSION_ALIGNMENT_CONFIG[editFormData.session_alignment].description}
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_description">描述（可选）</Label>
              <Textarea
                id="edit_description"
                placeholder="描述这个连接的用途..."
                value={editFormData.description}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, description: e.target.value })
                }
                maxLength={500}
                rows={3}
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
            <Button onClick={handleUpdateConnection} disabled={updating}>
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
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除连接？</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除从 <strong>{deletingConnection ? deletingConnection.source_node_id : ""}</strong> 到 <strong>{deletingConnection ? deletingConnection.target_node_id : ""}</strong> 的连接吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConnection}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  删除中...
                </>
              ) : (
                "删除"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
