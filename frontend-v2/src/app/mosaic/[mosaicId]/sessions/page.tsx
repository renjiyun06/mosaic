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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, MessageSquare, ChevronLeft, ChevronRight, Copy, Check, X } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import { SessionStatus, type NodeOut, type SessionOut } from "@/lib/types"

// Session status display configuration
const SESSION_STATUS_CONFIG: Record<SessionStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  [SessionStatus.ACTIVE]: { label: "活跃", variant: "default" },
  [SessionStatus.CLOSED]: { label: "已关闭", variant: "secondary" },
  [SessionStatus.ARCHIVED]: { label: "已归档", variant: "outline" },
}

export default function SessionsPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string

  // Mobile detection
  const [isMobile, setIsMobile] = useState(false)

  // Node list state
  const [nodes, setNodes] = useState<NodeOut[]>([])
  const [loadingNodes, setLoadingNodes] = useState(true)
  const [selectedNodeId, setSelectedNodeId] = useState<string>("all")

  // Session list state
  const [sessions, setSessions] = useState<SessionOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [sessionIdFilter, setSessionIdFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState<SessionStatus | "all">("all")

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)

  // Copy state
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null)

  // Mobile detection effect
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
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

  // Fetch sessions when node or filters change
  useEffect(() => {
    if (!token) {
      setSessions([])
      setTotal(0)
      setTotalPages(0)
      return
    }

    const fetchSessions = async () => {
      try {
        setLoading(true)
        setError(null)

        const params: any = {
          page: currentPage,
          page_size: pageSize,
        }

        if (sessionIdFilter.trim()) {
          params.session_id = sessionIdFilter.trim()
        }

        if (statusFilter !== "all") {
          params.status = statusFilter
        }

        const data = await apiClient.listSessions(
          Number(mosaicId),
          selectedNodeId === "all" ? undefined : selectedNodeId,
          params
        )

        setSessions(data.items)
        setTotal(data.total)
        setTotalPages(data.total_pages)
      } catch (err) {
        console.error("Failed to fetch sessions:", err)
        setError(err instanceof Error ? err.message : "Failed to load sessions")
        setSessions([])
        setTotal(0)
        setTotalPages(0)
      } finally {
        setLoading(false)
      }
    }

    fetchSessions()
  }, [mosaicId, selectedNodeId, currentPage, pageSize, sessionIdFilter, statusFilter, token])

  const handleNodeChange = (nodeId: string) => {
    setSelectedNodeId(nodeId)
    setCurrentPage(1) // Reset to first page when changing node
  }

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

  // Format cost for display
  const formatCost = (cost: number): string => {
    if (cost === 0) return "$0.00"
    if (cost < 0.01) return `$${cost.toFixed(4)}`
    return `$${cost.toFixed(2)}`
  }

  // Handle copy session ID
  const handleCopySessionId = async (sessionId: string) => {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(sessionId)
        setCopiedSessionId(sessionId)
        setTimeout(() => setCopiedSessionId(null), 1000)
      } else {
        // Fallback for older browsers or non-secure contexts
        const textArea = document.createElement("textarea")
        textArea.value = sessionId
        textArea.style.position = "fixed"
        textArea.style.left = "-999999px"
        textArea.style.top = "-999999px"
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()

        const successful = document.execCommand('copy')
        document.body.removeChild(textArea)

        if (successful) {
          setCopiedSessionId(sessionId)
          setTimeout(() => setCopiedSessionId(null), 1000)
        } else {
          throw new Error("Copy command failed")
        }
      }
    } catch (error) {
      console.error("Copy failed:", error)
    }
  }

  // Truncate session ID for display
  const truncateSessionId = (sessionId: string): string => {
    if (sessionId.length <= 16) return sessionId
    return `${sessionId.substring(0, 8)}...${sessionId.substring(sessionId.length - 8)}`
  }

  // Loading nodes state
  if (loadingNodes) {
    return (
      <div className="flex items-center justify-center min-h-[300px] sm:min-h-[400px]">
        <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // No nodes state
  if (nodes.length === 0) {
    return (
      <div className="flex flex-col h-full space-y-3 sm:space-y-4 md:space-y-6 overflow-auto">
        <div className="flex-shrink-0">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold">会话列表</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">查看和管理节点的会话记录</p>
        </div>
        <div className="flex-1 flex flex-col items-center pt-8 sm:pt-16 border rounded-lg px-4">
          <MessageSquare className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mb-3 sm:mb-4" />
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-center">还没有创建任何节点</h2>
          <p className="text-sm sm:text-base text-muted-foreground text-center mb-4 sm:mb-6 max-w-lg">
            请先创建节点，然后才能查看会话记录。
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-3 sm:space-y-4 md:space-y-6 overflow-auto">
      {/* Header */}
      <div className="flex-shrink-0">
        <h1 className="text-xl sm:text-2xl md:text-3xl font-bold">会话列表</h1>
        <p className="text-muted-foreground mt-1 text-sm md:text-base">查看和管理节点的会话记录</p>
      </div>

      {/* Filters */}
      <div className="flex-shrink-0 grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-3">
        {/* Node selector */}
        <Select value={selectedNodeId} onValueChange={handleNodeChange}>
          <SelectTrigger id="node-select">
            <SelectValue placeholder="选择节点" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部节点</SelectItem>
            {nodes.map((node) => (
              <SelectItem key={node.id} value={node.node_id}>
                {node.node_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Session ID filter */}
        <div className="relative">
          <Input
            id="session-id-filter"
            placeholder="搜索会话 ID..."
            value={sessionIdFilter}
            onChange={(e) => {
              setSessionIdFilter(e.target.value)
              setCurrentPage(1)
            }}
            className="pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          {sessionIdFilter && (
            <button
              onClick={() => {
                setSessionIdFilter("")
                setCurrentPage(1)
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Status filter */}
        <Select
          value={statusFilter}
          onValueChange={(value) => {
            setStatusFilter(value as SessionStatus | "all")
            setCurrentPage(1)
          }}
        >
          <SelectTrigger id="status-filter">
            <SelectValue placeholder="全部状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            {Object.entries(SESSION_STATUS_CONFIG).map(([status, config]) => (
              <SelectItem key={status} value={status}>
                {config.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Session list */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[300px] sm:min-h-[400px]">
          <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] sm:min-h-[400px] px-4">
          <p className="text-sm sm:text-base text-muted-foreground mb-4 text-center">{error}</p>
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex-1 flex flex-col items-center pt-8 sm:pt-16 border rounded-lg px-4">
          <MessageSquare className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mb-3 sm:mb-4" />
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-center">没有找到会话</h2>
          <p className="text-sm sm:text-base text-muted-foreground text-center mb-4 sm:mb-6 max-w-lg">
            {sessionIdFilter || statusFilter !== "all"
              ? "当前筛选条件下没有会话记录，请尝试调整筛选条件。"
              : "该节点还没有任何会话记录。"}
          </p>
        </div>
      ) : isMobile ? (
        // Mobile card view
        <div className="flex-1 overflow-auto space-y-3">
          {sessions.map((session) => (
            <Card key={session.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base font-mono text-sm break-all">
                      {session.session_id}
                    </CardTitle>
                  </div>
                  <button
                    onClick={() => handleCopySessionId(session.session_id)}
                    className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
                  >
                    {copiedSessionId === session.session_id ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-xs text-muted-foreground">节点</span>
                    <div className="font-mono text-sm mt-0.5">{session.node_id}</div>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">状态</span>
                    <div className="mt-0.5">
                      <Badge variant={SESSION_STATUS_CONFIG[session.status].variant} className="text-xs">
                        {SESSION_STATUS_CONFIG[session.status].label}
                      </Badge>
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">模式</span>
                    <div className="mt-0.5">
                      <Badge variant="outline" className="text-xs">{session.mode}</Badge>
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">模型</span>
                    <div className="mt-0.5">
                      <Badge variant="outline" className="text-xs">{session.model || "—"}</Badge>
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">消息数</span>
                    <div className="font-medium text-sm mt-0.5">{session.message_count}</div>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">成本</span>
                    <div className="font-mono text-sm mt-0.5">{formatCost(session.total_cost_usd)}</div>
                  </div>
                </div>
                <div className="space-y-1 text-xs">
                  <div>
                    <span className="text-muted-foreground">Token: </span>
                    <span className="font-mono">{session.total_input_tokens.toLocaleString()} / {session.total_output_tokens.toLocaleString()}</span>
                  </div>
                  <div className="text-muted-foreground">
                    最后活动: {new Date(session.last_activity_at).toLocaleString("zh-CN", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        // Desktop table view
        <>
          <div className="flex-1 flex flex-col min-h-0 border rounded-lg">
            <div className="flex-1 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-center">会话 ID</TableHead>
                    <TableHead className="text-center">节点 ID</TableHead>
                    <TableHead className="text-center">模式</TableHead>
                    <TableHead className="text-center">模型</TableHead>
                    <TableHead className="text-center">状态</TableHead>
                    <TableHead className="text-center">消息数</TableHead>
                    <TableHead className="text-center">Token (输入/输出)</TableHead>
                    <TableHead className="text-center">成本</TableHead>
                    <TableHead className="text-center">最后活动时间</TableHead>
                    <TableHead className="text-center">创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell className="text-center">
                        <div className="flex items-center justify-center gap-2">
                          <span className="font-mono text-sm">{truncateSessionId(session.session_id)}</span>
                          <button
                            onClick={() => handleCopySessionId(session.session_id)}
                            className="text-muted-foreground hover:text-foreground transition-colors"
                          >
                            {copiedSessionId === session.session_id ? (
                              <Check className="h-3.5 w-3.5 text-green-500" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{session.node_id}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{session.mode}</Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{session.model || "—"}</Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={SESSION_STATUS_CONFIG[session.status].variant}>
                          {SESSION_STATUS_CONFIG[session.status].label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{session.message_count}</Badge>
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {session.total_input_tokens.toLocaleString()} / {session.total_output_tokens.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-center text-sm font-mono">
                        {formatCost(session.total_cost_usd)}
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {new Date(session.last_activity_at).toLocaleString("zh-CN", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false
                        })}
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {new Date(session.created_at).toLocaleString("zh-CN", {
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

        </>
      )}

      {/* Pagination */}
      {totalPages > 1 && sessions.length > 0 && (
        <div className="flex-shrink-0 flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-4">
          <div className="text-xs sm:text-sm text-muted-foreground text-center sm:text-left">
            共 {total} 条记录，第 {currentPage} / {totalPages} 页
          </div>
          <div className="flex gap-2 w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousPage}
              disabled={currentPage === 1}
              className="flex-1 sm:flex-initial"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
              className="flex-1 sm:flex-initial"
            >
              下一页
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
