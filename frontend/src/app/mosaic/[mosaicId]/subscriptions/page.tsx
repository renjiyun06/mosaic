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
import { Plus, Trash2, Loader2, Edit, Bell, AlertCircle, Link2 } from "lucide-react"
import {
  apiClient,
  type NodeResponse,
  type ConnectionResponse,
  type SubscriptionResponse,
} from "@/lib/api"
import { useAuthStore } from "@/lib/store"
import {
  EventType,
  EVENT_TYPE_CONFIG,
  getEventTypeLabel,
} from "@/lib/enums"
import { EmptyState } from "@/components/ui/empty-state"

export default function SubscriptionsPage() {
  const params = useParams()
  const router = useRouter()
  const { token } = useAuthStore()
  const mosaicId = params.mosaicId as string

  const [subscriptions, setSubscriptions] = useState<SubscriptionResponse[]>([])
  const [connections, setConnections] = useState<ConnectionResponse[]>([])
  const [nodes, setNodes] = useState<NodeResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formData, setFormData] = useState({
    connectionId: "",
    source_node_id: "",
    target_node_id: "",
    event_type: EventType.SESSION_START,
    description: "",
  })

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingSubscription, setEditingSubscription] = useState<SubscriptionResponse | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editFormData, setEditFormData] = useState({
    description: "",
  })

  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingSubscription, setDeletingSubscription] = useState<SubscriptionResponse | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Fetch data
  useEffect(() => {
    if (!token) {
      router.push("/login")
      return
    }

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const [subscriptionsData, connectionsData, nodesData] = await Promise.all([
          apiClient.listSubscriptions(Number(mosaicId), token),
          apiClient.listConnections(Number(mosaicId), token),
          apiClient.listNodes(Number(mosaicId), token),
        ])
        setSubscriptions(subscriptionsData)
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

  const getConnectionLabel = (conn: ConnectionResponse): string => {
    return `${conn.source_node_id} → ${conn.target_node_id}`
  }

  const handleCreateSubscription = async () => {
    if (!token) return
    if (!formData.source_node_id || !formData.target_node_id || !formData.event_type) return

    try {
      setCreating(true)
      const requestData = {
        source_node_id: formData.source_node_id,
        target_node_id: formData.target_node_id,
        event_type: formData.event_type,
        description: formData.description || undefined,
      }
      await apiClient.createSubscription(Number(mosaicId), requestData, token)

      // Reset form and close dialog
      setFormData({
        connectionId: "",
        source_node_id: "",
        target_node_id: "",
        event_type: EventType.SESSION_START,
        description: "",
      })
      setCreateDialogOpen(false)

      // Refresh subscription list
      const data = await apiClient.listSubscriptions(Number(mosaicId), token)
      setSubscriptions(data)
    } catch (error) {
      console.error("Failed to create subscription:", error)
      const errorMessage = error instanceof Error ? error.message : "Failed to create subscription"
      alert(`创建订阅失败：${errorMessage}`)
    } finally {
      setCreating(false)
    }
  }

  const openEditDialog = (subscription: SubscriptionResponse) => {
    setEditingSubscription(subscription)
    setEditFormData({
      description: subscription.description || "",
    })
    setEditDialogOpen(true)
  }

  const handleUpdateSubscription = async () => {
    if (!token || !editingSubscription) return

    try {
      setUpdating(true)
      const requestData = {
        description: editFormData.description || undefined,
      }
      await apiClient.updateSubscription(
        Number(mosaicId),
        editingSubscription.id,
        requestData,
        token
      )

      // Close dialog
      setEditDialogOpen(false)
      setEditingSubscription(null)

      // Refresh subscription list
      const data = await apiClient.listSubscriptions(Number(mosaicId), token)
      setSubscriptions(data)
    } catch (error) {
      console.error("Failed to update subscription:", error)
      alert(error instanceof Error ? error.message : "Failed to update subscription")
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteSubscription = async () => {
    if (!token || !deletingSubscription) return

    try {
      setDeleting(true)
      await apiClient.deleteSubscription(
        Number(mosaicId),
        deletingSubscription.id,
        token
      )

      // Close dialog
      setDeleteDialogOpen(false)
      setDeletingSubscription(null)

      // Refresh subscription list
      const data = await apiClient.listSubscriptions(Number(mosaicId), token)
      setSubscriptions(data)
    } catch (error) {
      console.error("Failed to delete subscription:", error)
      alert(error instanceof Error ? error.message : "Failed to delete subscription")
    } finally {
      setDeleting(false)
    }
  }

  const openDeleteDialog = (subscription: SubscriptionResponse) => {
    setDeletingSubscription(subscription)
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
          <h1 className="text-3xl font-bold">事件订阅</h1>
          <p className="text-muted-foreground mt-1">在节点连接上定义要传递的事件类型</p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} disabled={connections.length === 0}>
          <Plus className="mr-2 h-4 w-4" />
          新建订阅
        </Button>
      </div>

      {subscriptions.length === 0 ? (
        connections.length === 0 ? (
          <EmptyState
            icon={AlertCircle}
            title="需要先创建节点连接"
            description="事件订阅必须建立在节点连接的基础上。请先在节点连接页面创建至少一个连接，然后再创建订阅。"
          />
        ) : (
          <EmptyState
            icon={Bell}
            title="还没有创建任何订阅"
            description="订阅定义了在节点连接上传递哪些类型的事件。创建第一个订阅来配置事件路由。"
            action={
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                创建第一个订阅
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
                <TableHead className="text-center">事件类型</TableHead>
                <TableHead className="text-center">描述</TableHead>
                <TableHead className="text-center">创建时间</TableHead>
                <TableHead className="text-center w-[120px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {subscriptions.map((subscription) => (
                <TableRow key={subscription.id}>
                  <TableCell className="text-center">
                    <div className="font-mono font-medium">
                      {subscription.source_node_id}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="font-mono font-medium">
                      {subscription.target_node_id}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline">
                      {getEventTypeLabel(subscription.event_type as EventType)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center text-sm text-muted-foreground">
                    {subscription.description || "暂无描述"}
                  </TableCell>
                  <TableCell className="text-center text-sm text-muted-foreground">
                    {new Date(subscription.created_at).toLocaleString("zh-CN", {
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
                        onClick={() => openEditDialog(subscription)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openDeleteDialog(subscription)}
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

      {/* Create Subscription Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>创建事件订阅</DialogTitle>
            <DialogDescription>
              在已有的节点连接上创建事件订阅
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="connection">节点连接 *</Label>
              <Select
                value={formData.connectionId}
                onValueChange={(value) => {
                  const connection = connections.find((c) => c.id === Number(value))
                  setFormData({
                    ...formData,
                    connectionId: value,
                    source_node_id: connection?.source_node_id || "",
                    target_node_id: connection?.target_node_id || "",
                  })
                }}
              >
                <SelectTrigger id="connection">
                  <SelectValue placeholder="选择节点连接" />
                </SelectTrigger>
                <SelectContent>
                  {connections.map((conn) => (
                    <SelectItem key={conn.id} value={String(conn.id)}>
                      {getConnectionLabel(conn)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                选择要在哪个连接上订阅事件
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="event_type">事件类型 *</Label>
              <Select
                value={formData.event_type}
                onValueChange={(value) =>
                  setFormData({ ...formData, event_type: value as EventType })
                }
              >
                <SelectTrigger id="event_type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(EventType).map((eventType) => (
                    <SelectItem key={eventType} value={eventType}>
                      {EVENT_TYPE_CONFIG[eventType].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {formData.event_type && EVENT_TYPE_CONFIG[formData.event_type].description}
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">描述（可选）</Label>
              <Textarea
                id="description"
                placeholder="描述这个订阅的用途..."
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
              onClick={handleCreateSubscription}
              disabled={creating || !formData.connectionId || !formData.event_type}
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

      {/* Edit Subscription Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑订阅</DialogTitle>
            <DialogDescription>
              更新订阅的描述信息
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>节点连接</Label>
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium font-mono">
                  {editingSubscription
                    ? editingSubscription.source_node_id
                    : ""}
                </span>
                <span className="text-muted-foreground">→</span>
                <span className="font-medium font-mono">
                  {editingSubscription
                    ? editingSubscription.target_node_id
                    : ""}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">连接关系创建后不可修改</p>
            </div>
            <div className="grid gap-2">
              <Label>事件类型</Label>
              <div className="text-sm">
                <Badge variant="outline">
                  {editingSubscription
                    ? getEventTypeLabel(editingSubscription.event_type as EventType)
                    : ""}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">事件类型创建后不可修改</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_description">描述（可选）</Label>
              <Textarea
                id="edit_description"
                placeholder="描述这个订阅的用途..."
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
            <Button onClick={handleUpdateSubscription} disabled={updating}>
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
            <AlertDialogTitle>确认删除订阅？</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除从{" "}
              <strong>
                {deletingSubscription
                  ? deletingSubscription.source_node_id
                  : ""}
              </strong>{" "}
              到{" "}
              <strong>
                {deletingSubscription
                  ? deletingSubscription.target_node_id
                  : ""}
              </strong>{" "}
              的{" "}
              <strong>
                {deletingSubscription
                  ? getEventTypeLabel(deletingSubscription.event_type as EventType)
                  : ""}
              </strong>{" "}
              事件订阅吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSubscription}
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
