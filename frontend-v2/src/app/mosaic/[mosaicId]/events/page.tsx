"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Loader2, Activity, ChevronLeft, ChevronRight, X } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { EventType, type NodeOut, type EventListOut, type EventDetailOut } from "@/lib/types"

// Event type display configuration
const EVENT_TYPE_CONFIG: Record<EventType, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  [EventType.SESSION_START]: { label: "会话开始", variant: "default" },
  [EventType.SESSION_RESPONSE]: { label: "会话响应", variant: "default" },
  [EventType.USER_PROMPT_SUBMIT]: { label: "用户提交", variant: "default" },
  [EventType.PRE_TOOL_USE]: { label: "工具调用前", variant: "secondary" },
  [EventType.POST_TOOL_USE]: { label: "工具调用后", variant: "secondary" },
  [EventType.SESSION_END]: { label: "会话结束", variant: "outline" },
  [EventType.NODE_MESSAGE]: { label: "节点消息", variant: "default" },
  [EventType.EVENT_BATCH]: { label: "事件批次", variant: "secondary" },
  [EventType.SYSTEM_MESSAGE]: { label: "系统消息", variant: "destructive" },
  [EventType.EMAIL_MESSAGE]: { label: "邮件消息", variant: "default" },
  [EventType.SCHEDULER_MESSAGE]: { label: "调度消息", variant: "default" },
  [EventType.REDDIT_SCRAPER_MESSAGE]: { label: "Reddit消息", variant: "default" },
  [EventType.USER_MESSAGE_EVENT]: { label: "用户消息事件", variant: "default" },
}

export default function EventsPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string

  // Node list state
  const [nodes, setNodes] = useState<NodeOut[]>([])
  const [loadingNodes, setLoadingNodes] = useState(true)

  // Event list state
  const [events, setEvents] = useState<EventListOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filter state - Time range (required)
  const [startDateTime, setStartDateTime] = useState("")
  const [endDateTime, setEndDateTime] = useState("")

  // Filter state - Optional filters
  const [sourceNodeId, setSourceNodeId] = useState<string>("all")
  const [sourceSessionId, setSourceSessionId] = useState("")
  const [targetNodeId, setTargetNodeId] = useState<string>("all")
  const [targetSessionId, setTargetSessionId] = useState("")
  const [eventType, setEventType] = useState<EventType | "all">("all")

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(100)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)

  // Event detail dialog state
  const [selectedEvent, setSelectedEvent] = useState<EventDetailOut | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Initialize time range to last 24 hours
  useEffect(() => {
    const now = new Date()
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)

    // Format to datetime-local input format: YYYY-MM-DDThh:mm
    const formatDateTime = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      return `${year}-${month}-${day}T${hours}:${minutes}`
    }

    setStartDateTime(formatDateTime(yesterday))
    setEndDateTime(formatDateTime(now))
  }, [])

  // Fetch nodes on mount
  useEffect(() => {
    if (!token) return

    const fetchNodes = async () => {
      try {
        setLoadingNodes(true)
        const data = await apiClient.listNodes(Number(mosaicId))
        setNodes(data)
      } catch (err) {
        console.error("Failed to fetch nodes:", err)
      } finally {
        setLoadingNodes(false)
      }
    }

    fetchNodes()
  }, [mosaicId, token])

  // Fetch events when filters change
  useEffect(() => {
    if (!token || !startDateTime || !endDateTime) {
      setEvents([])
      setTotal(0)
      setTotalPages(0)
      return
    }

    const fetchEvents = async () => {
      try {
        setLoading(true)
        setError(null)

        // Convert datetime-local to ISO string
        const start = new Date(startDateTime).toISOString()
        const end = new Date(endDateTime).toISOString()

        const params: any = {
          created_at_start: start,
          created_at_end: end,
          page: currentPage,
          page_size: pageSize,
        }

        if (sourceNodeId !== "all") {
          params.source_node_id = sourceNodeId
        }

        if (sourceSessionId.trim()) {
          params.source_session_id = sourceSessionId.trim()
        }

        if (targetNodeId !== "all") {
          params.target_node_id = targetNodeId
        }

        if (targetSessionId.trim()) {
          params.target_session_id = targetSessionId.trim()
        }

        if (eventType !== "all") {
          params.event_type = eventType
        }

        const data = await apiClient.listEvents(Number(mosaicId), params)

        setEvents(data.items)
        setTotal(data.total)
        setTotalPages(data.total_pages)
      } catch (err) {
        console.error("Failed to fetch events:", err)
        setError(err instanceof Error ? err.message : "Failed to load events")
        setEvents([])
        setTotal(0)
        setTotalPages(0)
      } finally {
        setLoading(false)
      }
    }

    fetchEvents()
  }, [
    mosaicId,
    token,
    startDateTime,
    endDateTime,
    sourceNodeId,
    sourceSessionId,
    targetNodeId,
    targetSessionId,
    eventType,
    currentPage,
    pageSize
  ])

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1)
    }
  }

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1)
    }
  }

  // Handle event click to show detail
  const handleEventClick = async (eventId: string) => {
    try {
      setLoadingDetail(true)
      const detail = await apiClient.getEvent(Number(mosaicId), eventId)
      setSelectedEvent(detail)
    } catch (err) {
      console.error("Failed to fetch event detail:", err)
    } finally {
      setLoadingDetail(false)
    }
  }

  // Truncate ID for display
  const truncateId = (id: string): string => {
    if (id.length <= 16) return id
    return `${id.substring(0, 8)}...${id.substring(id.length - 8)}`
  }

  // Loading nodes state
  if (loadingNodes) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Check if time range is valid
  const isTimeRangeValid = startDateTime && endDateTime && new Date(startDateTime) < new Date(endDateTime)

  return (
    <div className="flex flex-col h-full space-y-6 overflow-auto">
      {/* Header */}
      <div className="flex-shrink-0">
        <h1 className="text-3xl font-bold">事件监控</h1>
        <p className="text-muted-foreground mt-1">查看系统事件流历史记录</p>
      </div>

      {/* Filters */}
      <div className="flex-shrink-0 space-y-2">
        {/* First row: Source node, Source session, Target node, Target session */}
        <div className="grid gap-3 md:grid-cols-4">
          {/* Source node filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="source-node-filter" className="text-sm font-medium whitespace-nowrap w-16 flex-shrink-0">
              源节点
            </label>
            <div className="flex-1">
              <Select
                value={sourceNodeId}
                onValueChange={(value) => {
                  setSourceNodeId(value)
                  setCurrentPage(1)
                }}
              >
                <SelectTrigger id="source-node-filter" className="h-9 w-full">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部源节点</SelectItem>
                  {nodes.map((node) => (
                    <SelectItem key={node.id} value={node.node_id}>
                      {node.node_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Source session filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="source-session-filter" className="text-sm font-medium whitespace-nowrap w-16 flex-shrink-0">
              源会话
            </label>
            <div className="relative flex-1">
              <Input
                id="source-session-filter"
                placeholder="会话 ID..."
                value={sourceSessionId}
                onChange={(e) => {
                  setSourceSessionId(e.target.value)
                  setCurrentPage(1)
                }}
                className="h-9 pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
              />
              {sourceSessionId && (
                <button
                  onClick={() => {
                    setSourceSessionId("")
                    setCurrentPage(1)
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>

          {/* Target node filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="target-node-filter" className="text-sm font-medium whitespace-nowrap w-16 flex-shrink-0">
              目标节点
            </label>
            <div className="flex-1">
              <Select
                value={targetNodeId}
                onValueChange={(value) => {
                  setTargetNodeId(value)
                  setCurrentPage(1)
                }}
              >
                <SelectTrigger id="target-node-filter" className="h-9 w-full">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部目标节点</SelectItem>
                  {nodes.map((node) => (
                    <SelectItem key={node.id} value={node.node_id}>
                      {node.node_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Target session filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="target-session-filter" className="text-sm font-medium whitespace-nowrap w-16 flex-shrink-0">
              目标会话
            </label>
            <div className="relative flex-1">
              <Input
                id="target-session-filter"
                placeholder="会话 ID..."
                value={targetSessionId}
                onChange={(e) => {
                  setTargetSessionId(e.target.value)
                  setCurrentPage(1)
                }}
                className="h-9 pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
              />
              {targetSessionId && (
                <button
                  onClick={() => {
                    setTargetSessionId("")
                    setCurrentPage(1)
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Second row: Event type, Time range */}
        <div className="grid gap-3 md:grid-cols-4">
          {/* Event type filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="event-type-filter" className="text-sm font-medium whitespace-nowrap w-16 flex-shrink-0">
              事件类型
            </label>
            <div className="flex-1">
              <Select
                value={eventType}
                onValueChange={(value) => {
                  setEventType(value as EventType | "all")
                  setCurrentPage(1)
                }}
              >
                <SelectTrigger id="event-type-filter" className="h-9 w-full">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部类型</SelectItem>
                  {Object.entries(EVENT_TYPE_CONFIG).map(([type, config]) => (
                    <SelectItem key={type} value={type}>
                      {config.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Time range filter */}
          <div className="flex items-center gap-2 md:col-span-3">
            <label className="text-sm font-medium whitespace-nowrap w-16 flex-shrink-0">
              时间范围 <span className="text-destructive">*</span>
            </label>
            <Input
              id="start-time"
              type="datetime-local"
              value={startDateTime}
              onChange={(e) => {
                setStartDateTime(e.target.value)
                setCurrentPage(1)
              }}
              className="h-9 flex-1 text-right focus-visible:ring-0 focus-visible:ring-offset-0"
            />
            <span className="text-sm text-muted-foreground flex-shrink-0">至</span>
            <Input
              id="end-time"
              type="datetime-local"
              value={endDateTime}
              onChange={(e) => {
                setEndDateTime(e.target.value)
                setCurrentPage(1)
              }}
              className="h-9 flex-1 text-right focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </div>
        </div>
      </div>

      {/* Event list */}
      {!isTimeRangeValid ? (
        <div className="flex-1 flex flex-col items-center pt-16 border rounded-lg">
          <Activity className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">请选择有效的时间范围</h2>
          <p className="text-muted-foreground text-center mb-6 max-w-lg">
            开始时间必须早于结束时间。默认显示最近24小时的事件。
          </p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <p className="text-muted-foreground mb-4">{error}</p>
        </div>
      ) : events.length === 0 ? (
        <div className="flex-1 flex flex-col items-center pt-16 border rounded-lg">
          <Activity className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">没有找到事件</h2>
          <p className="text-muted-foreground text-center mb-6 max-w-lg">
            当前时间范围和筛选条件下没有事件记录。请尝试调整筛选条件。
          </p>
        </div>
      ) : (
        <>
          <div className="flex-1 flex flex-col min-h-0 border rounded-lg">
            <div className="flex-1 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-center">事件 ID</TableHead>
                    <TableHead className="text-center">事件类型</TableHead>
                    <TableHead className="text-center">源节点</TableHead>
                    <TableHead className="text-center">源会话</TableHead>
                    <TableHead className="text-center">目标节点</TableHead>
                    <TableHead className="text-center">目标会话</TableHead>
                    <TableHead className="text-center">创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => (
                    <TableRow key={event.event_id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell
                        className="text-center"
                        onClick={() => handleEventClick(event.event_id)}
                      >
                        <span className="font-mono text-sm text-primary hover:underline">
                          {truncateId(event.event_id)}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={EVENT_TYPE_CONFIG[event.event_type].variant}>
                          {EVENT_TYPE_CONFIG[event.event_type].label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{event.source_node_id}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{truncateId(event.source_session_id)}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{event.target_node_id}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{truncateId(event.target_session_id)}</span>
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {new Date(event.created_at).toLocaleString("zh-CN", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false
                        })}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex-shrink-0 flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                共 {total} 条记录，第 {currentPage} / {totalPages} 页
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePreviousPage}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                >
                  下一页
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Event Detail Dialog */}
      <Dialog open={!!selectedEvent} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-scroll">
          <DialogHeader>
            <DialogTitle>事件详情</DialogTitle>
          </DialogHeader>
          {loadingDetail ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : selectedEvent ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-1">事件 ID</h3>
                <p className="font-mono text-sm">{selectedEvent.event_id}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-1">事件类型</h3>
                <Badge variant={EVENT_TYPE_CONFIG[selectedEvent.event_type].variant}>
                  {EVENT_TYPE_CONFIG[selectedEvent.event_type].label}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-1">源节点 ID</h3>
                  <p className="font-mono text-sm">{selectedEvent.source_node_id}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-1">源会话 ID</h3>
                  <p className="font-mono text-sm">{selectedEvent.source_session_id}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-1">目标节点 ID</h3>
                  <p className="font-mono text-sm">{selectedEvent.target_node_id}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-1">目标会话 ID</h3>
                  <p className="font-mono text-sm">{selectedEvent.target_session_id}</p>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-1">创建时间</h3>
                <p className="text-sm">
                  {new Date(selectedEvent.created_at).toLocaleString("zh-CN", {
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false
                  })}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-1">Payload</h3>
                <pre className="bg-muted p-4 rounded-lg text-xs overflow-auto max-h-96">
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
