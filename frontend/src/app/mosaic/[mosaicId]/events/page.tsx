"use client"

import { useParams } from "next/navigation"
import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { apiClient, Event } from "@/lib/api"
import { getEventTypeLabel, EventType } from "@/lib/enums"
import { useAuthStore } from "@/lib/store"

export default function EventsPage() {
  const params = useParams()
  const mosaicId = parseInt(params.mosaicId as string)
  const { token } = useAuthStore()

  const [events, setEvents] = useState<Event[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // Filters
  const [eventType, setEventType] = useState<string>("all")
  const [sourceNodeId, setSourceNodeId] = useState<string>("")
  const [targetNodeId, setTargetNodeId] = useState<string>("")
  const [sessionId, setSessionId] = useState<string>("")

  // Pagination
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)

  const loadEvents = async () => {
    if (!token) return

    setLoading(true)
    try {
      const response = await apiClient.listEvents(mosaicId, token, {
        limit,
        offset,
        event_type: eventType === "all" ? undefined : eventType,
        source_node_id: sourceNodeId ? parseInt(sourceNodeId) : undefined,
        target_node_id: targetNodeId ? parseInt(targetNodeId) : undefined,
        session_id: sessionId || undefined,
      })
      setEvents(response.events)
      setTotal(response.total)
    } catch (error) {
      console.error("Failed to load events:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEvents()
  }, [mosaicId, token, offset, eventType, sourceNodeId, targetNodeId, sessionId])

  const handleReset = () => {
    setEventType("all")
    setSourceNodeId("")
    setTargetNodeId("")
    setSessionId("")
    setOffset(0)
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    })
  }

  const currentPage = Math.floor(offset / limit) + 1
  const totalPages = Math.ceil(total / limit)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">事件监控</h1>
          <p className="text-muted-foreground mt-1">
            监控和查看事件流转记录
          </p>
        </div>
        <Button onClick={loadEvents} disabled={loading}>
          {loading ? "加载中..." : "刷新"}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>筛选条件</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">事件类型</label>
            <Select value={eventType} onValueChange={setEventType}>
              <SelectTrigger>
                <SelectValue placeholder="全部" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部</SelectItem>
                {Object.values(EventType).map((type) => (
                  <SelectItem key={type} value={type}>
                    {getEventTypeLabel(type)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-sm font-medium mb-1 block">源节点ID</label>
            <Input
              type="number"
              placeholder="节点ID"
              value={sourceNodeId}
              onChange={(e) => setSourceNodeId(e.target.value)}
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-1 block">目标节点ID</label>
            <Input
              type="number"
              placeholder="节点ID"
              value={targetNodeId}
              onChange={(e) => setTargetNodeId(e.target.value)}
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-1 block">会话ID</label>
            <Input
              placeholder="会话ID"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
            />
          </div>

          <div className="md:col-span-4">
            <Button variant="outline" onClick={handleReset}>
              重置筛选
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Events Table */}
      <Card>
        <CardHeader>
          <CardTitle>事件列表 ({total} 条记录)</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>事件类型</TableHead>
                <TableHead>源节点</TableHead>
                <TableHead>目标节点</TableHead>
                <TableHead>上游会话</TableHead>
                <TableHead>下游会话</TableHead>
                <TableHead>时间</TableHead>
                <TableHead>载荷</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    {loading ? "加载中..." : "暂无事件"}
                  </TableCell>
                </TableRow>
              ) : (
                events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell>
                      {getEventTypeLabel(event.event_type as EventType)}
                    </TableCell>
                    <TableCell>{event.source_node_id}</TableCell>
                    <TableCell>{event.target_node_id}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {event.upstream_session_id?.slice(0, 8) || "-"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {event.downstream_session_id?.slice(0, 8) || "-"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {formatTimestamp(event.event_created_at)}
                    </TableCell>
                    <TableCell>
                      <pre className="text-xs max-w-xs overflow-auto">
                        {JSON.stringify(event.payload, null, 2)}
                      </pre>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-between items-center mt-4">
              <div className="text-sm text-muted-foreground">
                第 {currentPage} / {totalPages} 页
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                >
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= total}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
