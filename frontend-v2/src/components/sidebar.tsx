"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Box,
  Link2,
  Bell,
  MessageSquare,
  MessagesSquare,
  Mail,
  GitBranch,
  Activity,
  Settings,
  Play,
  Square,
  Circle,
  Loader2,
  Route,
  Network,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "./ui/button"
import { Badge } from "./ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import type { MosaicOut } from "@/lib/types"
import { MosaicStatus } from "@/lib/types"

interface SidebarProps {
  mosaicId: string
}

const navItems = [
  {
    title: "拓扑图",
    href: "/topology",
    icon: GitBranch,
  },
  {
    title: "节点管理",
    href: "/nodes",
    icon: Box,
  },
  {
    title: "节点连接",
    href: "/connections",
    icon: Link2,
  },
  {
    title: "事件订阅",
    href: "/subscriptions",
    icon: Bell,
  },
  {
    title: "会话路由",
    href: "/session-routings",
    icon: Route,
  },
  {
    title: "会话拓扑",
    href: "/session-topology",
    icon: Network,
  },
  {
    title: "会话列表",
    href: "/sessions",
    icon: MessageSquare,
  },
  {
    title: "会话消息",
    href: "/messages",
    icon: Mail,
  },
  {
    title: "实时对话",
    href: "/chat",
    icon: MessagesSquare,
  },
  {
    title: "事件监控",
    href: "/events",
    icon: Activity,
  },
  {
    title: "设置",
    href: "/settings",
    icon: Settings,
  },
]

export function Sidebar({ mosaicId }: SidebarProps) {
  const pathname = usePathname()
  const { token } = useAuth()
  const [mosaic, setMosaic] = useState<MosaicOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [operating, setOperating] = useState(false)
  const [stopConfirmOpen, setStopConfirmOpen] = useState(false)

  // Fetch mosaic data
  useEffect(() => {
    if (!token) return

    const fetchMosaic = async () => {
      try {
        setLoading(true)
        const data = await apiClient.getMosaic(parseInt(mosaicId))
        setMosaic(data)
      } catch (error) {
        console.error("Failed to fetch mosaic:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchMosaic()
  }, [mosaicId, token])

  const handleStart = async () => {
    if (!token || !mosaic) return

    try {
      setOperating(true)
      const updated = await apiClient.startMosaic(mosaic.id)
      setMosaic(updated)

      // Dispatch custom event to notify other components
      window.dispatchEvent(new CustomEvent('mosaic-status-changed', {
        detail: { status: updated.status, mosaicId: mosaic.id }
      }))
    } catch (error) {
      console.error("Failed to start mosaic:", error)
    } finally {
      setOperating(false)
    }
  }

  const handleStop = () => {
    setStopConfirmOpen(true)
  }

  const confirmStop = async () => {
    if (!token || !mosaic) return

    try {
      setOperating(true)
      const updated = await apiClient.stopMosaic(mosaic.id)
      setMosaic(updated)
      setStopConfirmOpen(false)

      // Dispatch custom event to notify other components
      window.dispatchEvent(new CustomEvent('mosaic-status-changed', {
        detail: { status: updated.status, mosaicId: mosaic.id }
      }))
    } catch (error) {
      console.error("Failed to stop mosaic:", error)
    } finally {
      setOperating(false)
    }
  }

  return (
    <>
      <div className="flex h-full w-64 flex-col border-r bg-background">
        {/* Mosaic Status Card */}
        <div className="border-b px-4 pt-4 pb-3">
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : mosaic ? (
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate">{mosaic.name}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">
                    {mosaic.description || `创建于 ${new Date(mosaic.created_at).toLocaleString("zh-CN", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                      hour12: false
                    })}`}
                  </p>
                </div>
                <Badge
                  variant={mosaic.status === MosaicStatus.RUNNING ? "default" : "secondary"}
                  className="ml-2"
                >
                  <Circle
                    className={cn(
                      "mr-1 h-2 w-2 fill-current",
                      mosaic.status === MosaicStatus.RUNNING && "text-green-500"
                    )}
                  />
                  {mosaic.status === MosaicStatus.RUNNING ? "运行中" : "已停止"}
                </Badge>
              </div>

              {mosaic.status === MosaicStatus.RUNNING ? (
                <Button
                  size="sm"
                  variant="destructive"
                  className="w-full"
                  onClick={handleStop}
                  disabled={operating}
                >
                  {operating ? (
                    <>
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                      停止中...
                    </>
                  ) : (
                    <>
                      <Square className="mr-1 h-3 w-3" />
                      停止 Mosaic
                    </>
                  )}
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="default"
                  className="w-full"
                  onClick={handleStart}
                  disabled={operating}
                >
                  {operating ? (
                    <>
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                      启动中...
                    </>
                  ) : (
                    <>
                      <Play className="mr-1 h-3 w-3" />
                      启动 Mosaic
                    </>
                  )}
                </Button>
              )}
            </div>
          ) : null}
        </div>

        {/* Navigation */}
        <div className="flex-1 space-y-1 px-4 pb-4 pt-4">
          <div className="mb-2 px-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            导航
          </div>
          {navItems.map((item) => {
            const href = `/mosaic/${mosaicId}${item.href}`
            const isActive = pathname === href || pathname.startsWith(href + "/")

            return (
              <Link
                key={item.href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all hover:bg-accent",
                  isActive
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            )
          })}
        </div>
      </div>

      {/* Stop Confirmation Dialog */}
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
                {mosaic?.name}
              </span> 吗？
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setStopConfirmOpen(false)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={confirmStop}
            >
              确认停止
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
