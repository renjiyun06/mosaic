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
  ChevronLeft,
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { useTheme } from "@/contexts/theme-context"
import type { MosaicOut } from "@/lib/types"
import { MosaicStatus } from "@/lib/types"

interface SidebarProps {
  mosaicId: string
  onNavigate?: () => void
  collapsed?: boolean
  onToggle?: () => void
  width?: number
  onWidthChange?: (width: number) => void
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

const MIN_WIDTH = 180
const MAX_WIDTH = 400
const COLLAPSE_THRESHOLD = 160 // Collapse instantly during drag
const EXPAND_THRESHOLD = 80 // Expand instantly during drag
const DEFAULT_WIDTH = 256 // 64 * 4 = w-64

export function Sidebar({
  mosaicId,
  onNavigate,
  collapsed = false,
  onToggle,
  width = DEFAULT_WIDTH,
  onWidthChange
}: SidebarProps) {
  const pathname = usePathname()
  const { token } = useAuth()
  const { theme } = useTheme()
  const [mosaic, setMosaic] = useState<MosaicOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [operating, setOperating] = useState(false)
  const [stopConfirmOpen, setStopConfirmOpen] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const [shouldAnimate, setShouldAnimate] = useState(true)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragStartWidth, setDragStartWidth] = useState(0)

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

  // Handle resize drag
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    setShouldAnimate(false) // Disable animation when starting drag
    setDragStartX(e.clientX)
    setDragStartWidth(collapsed ? 55 : width)
  }

  useEffect(() => {
    if (!isResizing || !onWidthChange) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - dragStartX
      const targetWidth = dragStartWidth + deltaX

      // Handle expansion from collapsed state
      if (collapsed) {
        if (targetWidth > EXPAND_THRESHOLD) {
          // Expand to minimum width smoothly
          onToggle?.()
          onWidthChange(MIN_WIDTH)
          // Update drag reference point to prevent jump
          setDragStartX(e.clientX)
          setDragStartWidth(MIN_WIDTH)
        }
        return
      }

      // Handle normal resizing when expanded
      if (targetWidth < COLLAPSE_THRESHOLD) {
        // Snap to collapsed state
        onToggle?.()
        // Update drag reference point
        setDragStartX(e.clientX)
        setDragStartWidth(55)
      } else {
        // Normal width adjustment
        const clampedWidth = Math.min(Math.max(targetWidth, MIN_WIDTH), MAX_WIDTH)
        onWidthChange(clampedWidth)
      }
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      // Re-enable animation after drag ends
      setTimeout(() => setShouldAnimate(true), 50)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing, collapsed, onToggle, onWidthChange, dragStartX, dragStartWidth])

  const currentWidth = collapsed ? 55 : width

  // Theme-aware sidebar classes
  const getSidebarClasses = () => {
    const baseClasses = "flex h-full w-full flex-col border-r overflow-y-auto overflow-x-hidden"

    switch (theme) {
      case 'cyberpunk':
        return `${baseClasses} backdrop-blur-xl bg-background/80 border-primary/30`
      case 'glassmorphism':
        return `${baseClasses} glass-card border-border/50`
      case 'terminal':
        return `${baseClasses} bg-background border-primary/40`
      default:
        return `${baseClasses} bg-background border-border`
    }
  }

  return (
    <>
      {/* Wrapper for sidebar and close button */}
      <div
        className={cn(
          "relative h-full",
          !isResizing && shouldAnimate && "transition-all duration-300"
        )}
        style={{ width: `${currentWidth}px` }}
      >
        {/* Mobile Close Button - Moved outside overflow container */}
        {onNavigate && (
          <button
            onClick={onNavigate}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-[60] rounded-full bg-background border shadow-md p-2 hover:bg-accent transition-colors lg:hidden"
            aria-label="关闭侧边栏"
          >
            <ChevronLeft className="h-4 w-4 icon-primary" />
          </button>
        )}

        {/* Resize handle - Desktop only */}
        {onWidthChange && (
          <div
            onMouseDown={handleMouseDown}
            className={cn(
              "absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-accent-foreground/20 active:bg-accent-foreground/30 transition-colors hidden lg:block z-50",
              isResizing && "bg-accent-foreground/30"
            )}
            aria-label="调整侧边栏宽度"
          />
        )}


        {/* Sidebar Content with overflow */}
        <div className={getSidebarClasses()}>
          {/* Mosaic Status Card */}
          <div
            className={cn(
              "border-b px-4 pt-4 pb-3 flex-shrink-0 overflow-hidden",
              collapsed && "opacity-0 h-0 py-0 border-0",
              !collapsed && shouldAnimate && "transition-all duration-300"
            )}
            style={{
              maxHeight: collapsed ? 0 : '300px',
              transition: shouldAnimate ? 'all 0.3s ease' : 'none'
            }}>
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground icon-secondary" />
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
                  className={cn(
                    "ml-2",
                    theme === 'cyberpunk' && mosaic.status === MosaicStatus.RUNNING &&
                      "bg-status-running/20 border border-status-running/50 text-status-running shadow-[0_0_12px_hsl(var(--status-running)/0.5)]"
                  )}
                >
                  <Circle
                    className={cn(
                      "mr-1 h-2 w-2 fill-current icon-success",
                      mosaic.status === MosaicStatus.RUNNING && "text-green-500",
                      theme === 'cyberpunk' && mosaic.status === MosaicStatus.RUNNING && "status-pulse"
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
                      <Loader2 className="mr-1 h-3 w-3 animate-spin icon-primary" />
                      停止中...
                    </>
                  ) : (
                    <>
                      <Square className="mr-1 h-3 w-3 icon-destructive" />
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
                      <Loader2 className="mr-1 h-3 w-3 animate-spin icon-primary" />
                      启动中...
                    </>
                  ) : (
                    <>
                      <Play className="mr-1 h-3 w-3 icon-success" />
                      启动 Mosaic
                    </>
                  )}
                </Button>
              )}
            </div>
          ) : null}
        </div>

        {/* Navigation */}
        <div className={cn(
          "flex-1 space-y-1 pb-4 pt-4 overflow-y-auto overflow-x-hidden",
          collapsed ? "px-1" : "px-4"
        )}>
          <div
            className={cn(
              "mb-2 px-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
              collapsed && "opacity-0 h-0 mb-0",
              !collapsed && shouldAnimate && "transition-all duration-300"
            )}
          >
            导航
          </div>
          {navItems.map((item) => {
            const href = `/mosaic/${mosaicId}${item.href}`
            const isActive = pathname === href || pathname.startsWith(href + "/")

            const linkContent = (
              <Link
                key={item.href}
                href={href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center rounded-lg px-3 py-2 text-sm transition-all hover:bg-accent",
                  collapsed ? "justify-center" : "gap-3",
                  isActive
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground",
                  theme === 'cyberpunk' && "hover:shadow-[0_0_16px_hsl(var(--primary)/0.3)] hover:border-l-2 hover:border-l-primary",
                  theme === 'glassmorphism' && "hover:backdrop-blur-xl"
                )}
              >
                <item.icon className={cn(
                  "h-4 w-4 shrink-0",
                  isActive ? "icon-primary" : "icon-secondary",
                  theme === 'cyberpunk' && isActive && "text-primary drop-shadow-[0_0_6px_hsl(var(--primary)/0.6)]"
                )} />
                {!collapsed && <span>{item.title}</span>}
              </Link>
            )

            if (collapsed) {
              return (
                <TooltipProvider key={item.href}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      {linkContent}
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      {item.title}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )
            }

            return linkContent
          })}
        </div>
      </div>
      </div>

      {/* Stop Confirmation Dialog */}
      <Dialog open={stopConfirmOpen} onOpenChange={setStopConfirmOpen}>
        <DialogContent className="sm:max-w-[425px] max-w-[calc(100vw-2rem)]">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">确认停止 Mosaic 实例</DialogTitle>
            <DialogDescription className="text-sm">
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
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setStopConfirmOpen(false)}
              className="w-full sm:w-auto"
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={confirmStop}
              className="w-full sm:w-auto"
            >
              确认停止
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
