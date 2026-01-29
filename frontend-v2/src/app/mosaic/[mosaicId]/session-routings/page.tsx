"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
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
import { Loader2, Route, ChevronLeft, ChevronRight, X, ArrowRight } from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import type { SessionRoutingOut, NodeOut } from "@/lib/types"

export default function SessionRoutingsPage() {
  const params = useParams()
  const { token } = useAuth()
  const mosaicId = params.mosaicId as string

  // Node list state
  const [nodes, setNodes] = useState<NodeOut[]>([])
  const [loadingNodes, setLoadingNodes] = useState(true)

  // Session routing list state
  const [routings, setRoutings] = useState<SessionRoutingOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Mobile detection
  const [isMobile, setIsMobile] = useState(false)

  // Filter state
  const [localNodeIdFilter, setLocalNodeIdFilter] = useState<string>("all")
  const [localSessionIdFilter, setLocalSessionIdFilter] = useState("")
  const [remoteNodeIdFilter, setRemoteNodeIdFilter] = useState<string>("all")
  const [remoteSessionIdFilter, setRemoteSessionIdFilter] = useState("")

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)

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

  // Fetch session routings when filters change
  useEffect(() => {
    if (!token) {
      setRoutings([])
      setTotal(0)
      setTotalPages(0)
      return
    }

    const fetchRoutings = async () => {
      try {
        setLoading(true)
        setError(null)

        const options: any = {
          page: currentPage,
          pageSize: pageSize,
        }

        if (localNodeIdFilter !== "all") {
          options.localNodeId = localNodeIdFilter
        }

        if (localSessionIdFilter.trim()) {
          options.localSessionId = localSessionIdFilter.trim()
        }

        if (remoteNodeIdFilter !== "all") {
          options.remoteNodeId = remoteNodeIdFilter
        }

        if (remoteSessionIdFilter.trim()) {
          options.remoteSessionId = remoteSessionIdFilter.trim()
        }

        const data = await apiClient.listSessionRoutings(Number(mosaicId), options)

        setRoutings(data.items)
        setTotal(data.total)
        setTotalPages(data.total_pages)
      } catch (err) {
        console.error("Failed to fetch session routings:", err)
        setError(err instanceof Error ? err.message : "Failed to load session routings")
        setRoutings([])
        setTotal(0)
        setTotalPages(0)
      } finally {
        setLoading(false)
      }
    }

    fetchRoutings()
  }, [
    mosaicId,
    currentPage,
    pageSize,
    localNodeIdFilter,
    localSessionIdFilter,
    remoteNodeIdFilter,
    remoteSessionIdFilter,
    token,
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

  const handleNodeFilterChange = (
    setter: React.Dispatch<React.SetStateAction<string>>,
    value: string
  ) => {
    setter(value)
    setCurrentPage(1) // Reset to first page when filter changes
  }

  const handleSessionIdFilterChange = (
    setter: React.Dispatch<React.SetStateAction<string>>,
    value: string
  ) => {
    setter(value)
    setCurrentPage(1) // Reset to first page when filter changes
  }

  // Loading nodes state
  if (loadingNodes) {
    return (
      <div className="flex items-center justify-center min-h-[300px] sm:min-h-[400px]">
        <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-3 sm:space-y-4 md:space-y-6 overflow-auto">
      {/* Header */}
      <div className="flex-shrink-0">
        <h1 className="text-xl sm:text-2xl md:text-3xl font-bold">会话路由</h1>
        <p className="text-muted-foreground mt-1 text-sm md:text-base">查看节点间的会话路由映射关系</p>
      </div>

      {/* Filters */}
      <div className="flex-shrink-0 grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {/* Local Node ID filter */}
        <Select
          value={localNodeIdFilter}
          onValueChange={(value) => handleNodeFilterChange(setLocalNodeIdFilter, value)}
        >
          <SelectTrigger id="local-node-filter">
            <SelectValue placeholder="本地节点" />
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

        {/* Local Session ID filter */}
        <div className="relative">
          <Input
            id="local-session-id-filter"
            placeholder="本地会话 ID..."
            value={localSessionIdFilter}
            onChange={(e) => handleSessionIdFilterChange(setLocalSessionIdFilter, e.target.value)}
            className="pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          {localSessionIdFilter && (
            <button
              onClick={() => handleSessionIdFilterChange(setLocalSessionIdFilter, "")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Remote Node ID filter */}
        <Select
          value={remoteNodeIdFilter}
          onValueChange={(value) => handleNodeFilterChange(setRemoteNodeIdFilter, value)}
        >
          <SelectTrigger id="remote-node-filter">
            <SelectValue placeholder="远程节点" />
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

        {/* Remote Session ID filter */}
        <div className="relative">
          <Input
            id="remote-session-id-filter"
            placeholder="远程会话 ID..."
            value={remoteSessionIdFilter}
            onChange={(e) => handleSessionIdFilterChange(setRemoteSessionIdFilter, e.target.value)}
            className="pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          {remoteSessionIdFilter && (
            <button
              onClick={() => handleSessionIdFilterChange(setRemoteSessionIdFilter, "")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Session routing list */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[300px] sm:min-h-[400px]">
          <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] sm:min-h-[400px] px-4">
          <p className="text-muted-foreground mb-4 text-sm sm:text-base text-center">{error}</p>
        </div>
      ) : routings.length === 0 ? (
        <div className="flex-1 flex flex-col items-center pt-8 sm:pt-16 border rounded-lg px-4">
          <Route className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mb-3 sm:mb-4" />
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-center">没有找到会话路由</h2>
          <p className="text-muted-foreground text-center mb-4 sm:mb-6 max-w-lg text-sm sm:text-base">
            {localNodeIdFilter !== "all" ||
            localSessionIdFilter ||
            remoteNodeIdFilter !== "all" ||
            remoteSessionIdFilter
              ? "当前筛选条件下没有会话路由记录，请尝试调整筛选条件。"
              : "该 Mosaic 还没有任何会话路由记录。"}
          </p>
        </div>
      ) : isMobile ? (
        // Mobile card view
        <div className="flex-1 overflow-auto space-y-3">
          {routings.map((routing, index) => (
            <Card key={index}>
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold">路由记录</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground min-w-[60px]">本地节点：</span>
                    <span className="font-mono text-sm break-all flex-1">{routing.local_node_id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground min-w-[60px]">本地会话：</span>
                    <span className="font-mono text-xs break-all flex-1">{routing.local_session_id}</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground min-w-[60px]">远程节点：</span>
                    <span className="font-mono text-sm break-all flex-1">{routing.remote_node_id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground min-w-[60px]">远程会话：</span>
                    <span className="font-mono text-xs break-all flex-1">{routing.remote_session_id}</span>
                  </div>
                </div>
                <div className="text-xs text-muted-foreground pt-2 border-t">
                  创建于 {new Date(routing.created_at).toLocaleString("zh-CN", {
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false,
                  })}
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
                    <TableHead className="text-center">本地节点 ID</TableHead>
                    <TableHead className="text-center">本地会话 ID</TableHead>
                    <TableHead className="text-center">远程节点 ID</TableHead>
                    <TableHead className="text-center">远程会话 ID</TableHead>
                    <TableHead className="text-center">创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {routings.map((routing, index) => (
                    <TableRow key={index}>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{routing.local_node_id}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{routing.local_session_id}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{routing.remote_node_id}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{routing.remote_session_id}</span>
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {new Date(routing.created_at).toLocaleString("zh-CN", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false,
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
      {totalPages > 1 && routings.length > 0 && (
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
