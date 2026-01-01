"use client"

/**
 * Home Page - Mosaic List
 * Displays all mosaic instances for the current user
 */

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Plus, Circle, Loader2, Play, Square, Edit, Trash2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Navbar } from "@/components/navbar"
import { AuthGuard } from "@/components/auth-guard"
import { cn } from "@/lib/utils"
import { apiClient } from "@/lib/api"
import type { MosaicOut } from "@/lib/types"

function HomePage() {
  const router = useRouter()
  const [mosaics, setMosaics] = useState<MosaicOut[]>([])
  const [loading, setLoading] = useState(true)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [stopConfirmOpen, setStopConfirmOpen] = useState(false)
  const [mosaicToStop, setMosaicToStop] = useState<number | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingMosaicId, setEditingMosaicId] = useState<number | null>(null)
  const [updating, setUpdating] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [mosaicToDelete, setMosaicToDelete] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [formData, setFormData] = useState({
    name: "",
    description: "",
  })

  // Fetch mosaics
  useEffect(() => {
    const fetchMosaics = async () => {
      try {
        setLoading(true)
        const data = await apiClient.listMosaics()
        setMosaics(data)
      } catch (error) {
        console.error("Failed to fetch mosaics:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchMosaics()
  }, [])

  const handleCreateMosaic = async () => {
    if (!formData.name.trim()) return

    try {
      setCreating(true)
      await apiClient.createMosaic({
        name: formData.name,
        description: formData.description || undefined,
      })

      // Reset form and close dialog
      setFormData({ name: "", description: "" })
      setCreateDialogOpen(false)

      // Refresh mosaic list
      const data = await apiClient.listMosaics()
      setMosaics(data)
    } catch (error) {
      console.error("Failed to create mosaic:", error)
    } finally {
      setCreating(false)
    }
  }

  const handleStartMosaic = async (mosaicId: number, e: React.MouseEvent) => {
    e.preventDefault() // Prevent Link navigation

    try {
      await apiClient.startMosaic(mosaicId)
      // Refresh mosaic list
      const data = await apiClient.listMosaics()
      setMosaics(data)
    } catch (error) {
      console.error("Failed to start mosaic:", error)
    }
  }

  const handleStopMosaic = (mosaicId: number, e: React.MouseEvent) => {
    e.preventDefault() // Prevent Link navigation
    setMosaicToStop(mosaicId)
    setStopConfirmOpen(true)
  }

  const confirmStopMosaic = async () => {
    if (mosaicToStop === null) return

    try {
      await apiClient.stopMosaic(mosaicToStop)
      // Refresh mosaic list
      const data = await apiClient.listMosaics()
      setMosaics(data)
      setStopConfirmOpen(false)
      setMosaicToStop(null)
    } catch (error) {
      console.error("Failed to stop mosaic:", error)
    }
  }

  const handleEditMosaic = (mosaic: MosaicOut, e: React.MouseEvent) => {
    e.preventDefault() // Prevent Link navigation
    setEditingMosaicId(mosaic.id)
    setFormData({
      name: mosaic.name,
      description: mosaic.description || "",
    })
    setEditDialogOpen(true)
  }

  const handleUpdateMosaic = async () => {
    if (editingMosaicId === null) return
    if (!formData.name.trim()) return

    try {
      setUpdating(true)
      await apiClient.updateMosaic(editingMosaicId, {
        name: formData.name,
        description: formData.description || undefined,
      })

      // Reset form and close dialog
      setFormData({ name: "", description: "" })
      setEditDialogOpen(false)
      setEditingMosaicId(null)

      // Refresh mosaic list
      const data = await apiClient.listMosaics()
      setMosaics(data)
    } catch (error) {
      console.error("Failed to update mosaic:", error)
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteMosaic = (mosaicId: number, e: React.MouseEvent) => {
    e.preventDefault() // Prevent Link navigation
    setMosaicToDelete(mosaicId)
    setDeleteConfirmOpen(true)
  }

  const confirmDeleteMosaic = async () => {
    if (mosaicToDelete === null) return

    try {
      setDeleting(true)
      await apiClient.deleteMosaic(mosaicToDelete)
      // Refresh mosaic list
      const data = await apiClient.listMosaics()
      setMosaics(data)
      setDeleteConfirmOpen(false)
      setMosaicToDelete(null)
    } catch (error) {
      console.error("Failed to delete mosaic:", error)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="container mx-auto px-4 py-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold">Mosaic 实例</h1>
              <p className="mt-2 text-muted-foreground">
                管理你的事件驱动多智能体系统实例
              </p>
            </div>
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              新建 Mosaic
            </Button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : mosaics.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <p className="text-muted-foreground mb-4">还没有创建任何 Mosaic 实例</p>
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                创建第一个 Mosaic
              </Button>
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {mosaics.map((mosaic) => (
                <Link key={mosaic.id} href={`/mosaic/${mosaic.id}/nodes`}>
                  <Card className="h-full transition-all hover:shadow-lg hover:border-primary/50">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <CardTitle className="text-xl">{mosaic.name}</CardTitle>
                          <CardDescription className="mt-1.5 text-xs text-muted-foreground">
                            ID: {mosaic.id}
                          </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            节点: {mosaic.node_count}
                          </Badge>
                          <Badge
                            variant={
                              mosaic.status === "running" ? "default" : "secondary"
                            }
                          >
                            <Circle
                              className={cn(
                                "mr-1 h-2 w-2 fill-current",
                                mosaic.status === "running" && "text-green-500"
                              )}
                            />
                            {mosaic.status === "running" ? "运行中" : "已停止"}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-4">
                        {mosaic.description || "暂无描述"}
                      </p>
                      <div className="flex items-center justify-end text-xs text-muted-foreground mb-4">
                        创建于 {new Date(mosaic.created_at).toLocaleString("zh-CN", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false
                        })}
                      </div>
                      <div className="flex gap-2" onClick={(e) => e.preventDefault()}>
                        {mosaic.status === "running" ? (
                          <Button
                            size="sm"
                            variant="destructive"
                            className="flex-1"
                            onClick={(e) => handleStopMosaic(mosaic.id, e)}
                          >
                            <Square className="mr-1 h-3 w-3" />
                            停止
                          </Button>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="default"
                              className="flex-1"
                              onClick={(e) => handleStartMosaic(mosaic.id, e)}
                            >
                              <Play className="mr-1 h-3 w-3" />
                              启动
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => handleEditMosaic(mosaic, e)}
                            >
                              <Edit className="h-3 w-3" />
                            </Button>
                            {mosaic.node_count > 0 ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="text-destructive hover:text-destructive"
                                    disabled
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>此 Mosaic 有 {mosaic.node_count} 个节点</p>
                                  <p className="text-xs text-muted-foreground">需要先删除所有节点</p>
                                </TooltipContent>
                              </Tooltip>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-destructive hover:text-destructive"
                                onClick={(e) => handleDeleteMosaic(mosaic.id, e)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            )}
                          </>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Create Mosaic Dialog */}
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>创建新的 Mosaic 实例</DialogTitle>
              <DialogDescription>
                创建一个新的事件驱动多智能体系统实例
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="name">名称 *</Label>
                <Input
                  id="name"
                  placeholder="例如:生产环境、开发测试"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  maxLength={100}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="description">描述(可选)</Label>
                <Textarea
                  id="description"
                  placeholder="描述这个 Mosaic 实例的用途..."
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
                onClick={handleCreateMosaic}
                disabled={creating || !formData.name.trim()}
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

        {/* Edit Mosaic Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>编辑 Mosaic 实例</DialogTitle>
              <DialogDescription>
                修改 Mosaic 实例的名称和描述
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-name">名称 *</Label>
                <Input
                  id="edit-name"
                  placeholder="例如:生产环境、开发测试"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  maxLength={100}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-description">描述(可选)</Label>
                <Textarea
                  id="edit-description"
                  placeholder="描述这个 Mosaic 实例的用途..."
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
                onClick={() => {
                  setEditDialogOpen(false)
                  setEditingMosaicId(null)
                  setFormData({ name: "", description: "" })
                }}
                disabled={updating}
              >
                取消
              </Button>
              <Button
                onClick={handleUpdateMosaic}
                disabled={updating || !formData.name.trim()}
              >
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

        {/* Stop Mosaic Confirmation Dialog */}
        <Dialog open={stopConfirmOpen} onOpenChange={setStopConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>确认停止 Mosaic 实例</DialogTitle>
              <DialogDescription>
                停止运行中的 Mosaic 实例将会终止所有正在运行的节点。此操作可以随时重新启动。
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <p className="text-sm text-muted-foreground">
                你确定要停止 <span className="font-semibold text-foreground">
                  {mosaics.find((m) => m.id === mosaicToStop)?.name}
                </span> 吗?
              </p>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setStopConfirmOpen(false)
                  setMosaicToStop(null)
                }}
              >
                取消
              </Button>
              <Button
                variant="destructive"
                onClick={confirmStopMosaic}
              >
                确认停止
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Mosaic Confirmation Dialog */}
        <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <DialogContent>
            {(() => {
              const targetMosaic = mosaics.find((m) => m.id === mosaicToDelete)
              const hasNodes = (targetMosaic?.node_count || 0) > 0

              return hasNodes ? (
                <>
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <AlertCircle className="h-5 w-5 text-destructive" />
                      无法删除 Mosaic 实例
                    </DialogTitle>
                    <DialogDescription>
                      此 Mosaic 实例下仍有节点存在,必须先删除所有节点才能删除实例。
                    </DialogDescription>
                  </DialogHeader>
                  <div className="py-4 space-y-4">
                    <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 space-y-2">
                      <p className="text-sm font-semibold text-amber-600">
                        当前状态
                      </p>
                      <ul className="text-sm text-muted-foreground space-y-1">
                        <li>Mosaic 名称: <span className="font-semibold text-foreground">{targetMosaic?.name}</span></li>
                        <li>节点数量: <span className="font-semibold text-foreground">{targetMosaic?.node_count}</span></li>
                      </ul>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      请先前往节点管理页面删除所有节点,然后再尝试删除此 Mosaic 实例。
                    </p>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setDeleteConfirmOpen(false)
                        setMosaicToDelete(null)
                      }}
                    >
                      取消
                    </Button>
                    <Button
                      onClick={() => {
                        setDeleteConfirmOpen(false)
                        setMosaicToDelete(null)
                        router.push(`/mosaic/${mosaicToDelete}/nodes`)
                      }}
                    >
                      前往节点管理
                    </Button>
                  </DialogFooter>
                </>
              ) : (
                <>
                  <DialogHeader>
                    <DialogTitle>确认删除 Mosaic 实例</DialogTitle>
                    <DialogDescription>
                      删除 Mosaic 实例是不可逆的操作,将永久删除该实例及其所有配置。
                    </DialogDescription>
                  </DialogHeader>
                  <div className="py-4 space-y-4">
                    <p className="text-sm text-muted-foreground">
                      你确定要删除 <span className="font-semibold text-foreground">
                        {targetMosaic?.name}
                      </span> 吗?
                    </p>
                    <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 space-y-2">
                      <p className="text-sm font-semibold text-destructive">警告</p>
                      <p className="text-sm text-muted-foreground">
                        此操作无法撤销,所有关联的配置和数据都将被永久删除。
                      </p>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setDeleteConfirmOpen(false)
                        setMosaicToDelete(null)
                      }}
                      disabled={deleting}
                    >
                      取消
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={confirmDeleteMosaic}
                      disabled={deleting}
                    >
                      {deleting ? (
                        <>
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          删除中...
                        </>
                      ) : (
                        "确认删除"
                      )}
                    </Button>
                  </DialogFooter>
                </>
              )
            })()}
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  )
}

export default function Home() {
  return (
    <AuthGuard>
      <HomePage />
    </AuthGuard>
  )
}
