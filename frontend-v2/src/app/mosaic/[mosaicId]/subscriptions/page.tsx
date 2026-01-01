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
import { Plus, Trash2, Loader2, Edit, ArrowRight, Bell } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { EventType, type ConnectionOut, type SubscriptionOut } from "@/lib/types"

// Event type display configuration
const EVENT_TYPE_LABELS: Record<EventType, string> = {
  [EventType.SESSION_START]: "会话启动",
  [EventType.SESSION_RESPONSE]: "会话响应",
  [EventType.USER_PROMPT_SUBMIT]: "用户提交",
  [EventType.PRE_TOOL_USE]: "工具调用前",
  [EventType.POST_TOOL_USE]: "工具调用后",
  [EventType.SESSION_END]: "会话结束",
  [EventType.NODE_MESSAGE]: "节点消息",
  [EventType.EVENT_BATCH]: "事件批次",
  [EventType.SYSTEM_MESSAGE]: "系统消息",
  [EventType.EMAIL_MESSAGE]: "邮件消息",
  [EventType.SCHEDULER_MESSAGE]: "调度消息",
  [EventType.REDDIT_SCRAPER_MESSAGE]: "Reddit抓取",
  [EventType.USER_MESSAGE_EVENT]: "用户消息事件",
}

// Event types that can be subscribed to (excluding system events)
const SUBSCRIBABLE_EVENT_TYPES = Object.entries(EVENT_TYPE_LABELS).filter(
  ([type]) =>
    type !== EventType.SYSTEM_MESSAGE &&
    type !== EventType.USER_MESSAGE_EVENT &&
    type !== EventType.NODE_MESSAGE
)

export default function SubscriptionsPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string

  const [subscriptions, setSubscriptions] = useState<SubscriptionOut[]>([])
  const [connections, setConnections] = useState<ConnectionOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formData, setFormData] = useState({
    connection_id: "",
    event_type: EventType.SESSION_START,
    description: "",
  })

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingSubscription, setEditingSubscription] = useState<SubscriptionOut | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editFormData, setEditFormData] = useState({
    description: "",
  })

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingSubscription, setDeletingSubscription] = useState<SubscriptionOut | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Fetch subscriptions and connections
  useEffect(() => {
    if (!token) return

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const [subscriptionsData, connectionsData] = await Promise.all([
          apiClient.listSubscriptions(Number(mosaicId)),
          apiClient.listConnections(Number(mosaicId)),
        ])
        setSubscriptions(subscriptionsData)
        setConnections(connectionsData)
      } catch (err) {
        console.error("Failed to fetch data:", err)
        setError(err instanceof Error ? err.message : "Failed to load data")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [mosaicId, token])

  const handleCreateSubscription = async () => {
    if (!token) return
    if (!formData.connection_id) return

    try {
      setCreating(true)
      const requestData = {
        connection_id: Number(formData.connection_id),
        event_type: formData.event_type,
        description: formData.description || undefined,
      }
      await apiClient.createSubscription(Number(mosaicId), requestData)

      // Reset form and close dialog
      setFormData({
        connection_id: "",
        event_type: EventType.SESSION_START,
        description: "",
      })
      setCreateDialogOpen(false)

      // Refresh subscription list
      const data = await apiClient.listSubscriptions(Number(mosaicId))
      setSubscriptions(data)
    } catch (error) {
      console.error("Failed to create subscription:", error)
      alert(error instanceof Error ? error.message : "Failed to create subscription")
    } finally {
      setCreating(false)
    }
  }

  const openEditDialog = (subscription: SubscriptionOut) => {
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
        requestData
      )

      // Close dialog
      setEditDialogOpen(false)
      setEditingSubscription(null)

      // Refresh subscription list
      const data = await apiClient.listSubscriptions(Number(mosaicId))
      setSubscriptions(data)
    } catch (error) {
      console.error("Failed to update subscription:", error)
      alert(error instanceof Error ? error.message : "Failed to update subscription")
    } finally {
      setUpdating(false)
    }
  }

  const openDeleteDialog = (subscription: SubscriptionOut) => {
    setDeletingSubscription(subscription)
    setDeleteDialogOpen(true)
  }

  const handleDeleteSubscription = async () => {
    if (!token || !deletingSubscription) return

    try {
      setDeleting(true)
      await apiClient.deleteSubscription(Number(mosaicId), deletingSubscription.id)

      setDeleteDialogOpen(false)
      setDeletingSubscription(null)

      // Refresh subscription list
      const data = await apiClient.listSubscriptions(Number(mosaicId))
      setSubscriptions(data)
    } catch (error) {
      console.error("Failed to delete subscription:", error)
      alert(error instanceof Error ? error.message : "Failed to delete subscription")
    } finally {
      setDeleting(false)
    }
  }

  // Get connection display name
  const getConnectionDisplay = (connectionId: number) => {
    const connection = connections.find((c) => c.id === connectionId)
    if (!connection) return `连接 #${connectionId}`
    return `${connection.source_node_id} → ${connection.target_node_id}`
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
    <div className="flex flex-col h-full space-y-6 overflow-auto">
      <div className="flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">事件订阅</h1>
            <p className="text-muted-foreground mt-1">管理节点之间的事件订阅关系</p>
          </div>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            disabled={connections.length === 0}
          >
            <Plus className="mr-2 h-4 w-4" />
            新建订阅
          </Button>
        </div>
      </div>

      {subscriptions.length === 0 ? (
        <div className="flex-1 flex flex-col items-center pt-16 border rounded-lg">
          <Bell className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">还没有创建任何订阅</h2>
          <p className="text-muted-foreground text-center mb-6 max-w-lg">
            事件订阅定义了节点之间的消息传递规则。<br />
            {connections.length > 0 ? (
              "在已有的连接上创建订阅，指定要传递的事件类型。"
            ) : (
              "请先创建节点连接，然后才能创建事件订阅。"
            )}
          </p>
          {connections.length > 0 && (
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              创建第一个订阅
            </Button>
          )}
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0 border rounded-lg">
          <div className="flex-1 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-center">源节点</TableHead>
                  <TableHead className="text-center w-12"></TableHead>
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
                      <span className="font-medium font-mono">{subscription.source_node_id}</span>
                    </TableCell>
                    <TableCell className="text-center">
                      <ArrowRight className="h-4 w-4 text-muted-foreground mx-auto" />
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="font-medium font-mono">{subscription.target_node_id}</span>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">
                        {EVENT_TYPE_LABELS[subscription.event_type]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center max-w-xs truncate text-sm text-muted-foreground">
                      {subscription.description || "—"}
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
                          title="编辑订阅"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openDeleteDialog(subscription)}
                          title="删除订阅"
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

      {/* Create Subscription Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-scroll">
          <DialogHeader>
            <DialogTitle>创建新订阅</DialogTitle>
            <DialogDescription>
              在已有的连接上创建事件订阅
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="connection_id">连接 *</Label>
              <Select
                value={formData.connection_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, connection_id: value })
                }
              >
                <SelectTrigger id="connection_id">
                  <SelectValue placeholder="选择一个连接" />
                </SelectTrigger>
                <SelectContent>
                  {connections.length === 0 ? (
                    <div className="px-2 py-3 text-sm text-muted-foreground text-center">
                      暂无可用连接
                    </div>
                  ) : (
                    connections.map((connection) => (
                      <SelectItem key={connection.id} value={String(connection.id)}>
                        {connection.source_node_id} → {connection.target_node_id}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {connections.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  请先在"节点连接"页面创建连接
                </p>
              )}
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
                  {SUBSCRIBABLE_EVENT_TYPES.map(([type, label]) => (
                    <SelectItem key={type} value={type}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                maxLength={1000}
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
              disabled={creating || !formData.connection_id || connections.length === 0}
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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-scroll">
          <DialogHeader>
            <DialogTitle>编辑订阅</DialogTitle>
            <DialogDescription>
              更新订阅的描述信息
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>连接</Label>
              <div className="px-3 py-2 bg-muted rounded-md text-sm">
                {editingSubscription && getConnectionDisplay(editingSubscription.connection_id)}
              </div>
            </div>
            <div className="grid gap-2">
              <Label>事件类型</Label>
              <div className="px-3 py-2 bg-muted rounded-md text-sm">
                {editingSubscription && EVENT_TYPE_LABELS[editingSubscription.event_type]}
              </div>
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
                maxLength={1000}
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
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除订阅？</DialogTitle>
            <DialogDescription>
              此操作将删除事件订阅。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          {deletingSubscription && (
            <div className="py-4">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">连接：</span>
                  <span className="font-medium">
                    {deletingSubscription.source_node_id} → {deletingSubscription.target_node_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">事件类型：</span>
                  <span className="font-medium">
                    {EVENT_TYPE_LABELS[deletingSubscription.event_type]}
                  </span>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteSubscription}
              disabled={deleting}
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
