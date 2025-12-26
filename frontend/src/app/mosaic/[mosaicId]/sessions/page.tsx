"use client"

/**
 * Sessions List Page - Session management with table view
 *
 * Features:
 * - Table view of all sessions
 * - Multi-dimensional filtering (node, status, time)
 * - Search by session ID
 * - Pagination
 * - Jump to chat page to continue conversation
 * - Archive/unarchive/delete operations
 */

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
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
  MessageSquare,
  Search,
  Archive,
  ArchiveRestore,
  Trash2,
  Eye,
  Loader2,
  Filter,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { useAuthStore } from "@/lib/store"
import { apiClient, SessionResponse, NodeResponse } from "@/lib/api"

export default function SessionsListPage() {
  const params = useParams()
  const router = useRouter()
  const mosaicId = parseInt(params.mosaicId as string)
  const { token } = useAuthStore()

  // Data
  const [sessions, setSessions] = useState<SessionResponse[]>([])
  const [total, setTotal] = useState(0)
  const [nodes, setNodes] = useState<NodeResponse[]>([])
  const [loading, setLoading] = useState(true)

  // Filters
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedNodeId, setSelectedNodeId] = useState<string>("all")
  const [selectedStatus, setSelectedStatus] = useState<string>("all")

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 20

  // Load data
  useEffect(() => {
    if (token) {
      loadData()
    }
  }, [mosaicId, token, selectedNodeId, selectedStatus, currentPage])

  const loadData = async () => {
    try {
      setLoading(true)

      // Load nodes (for filter dropdown)
      const nodesData = await apiClient.listNodes(mosaicId, token!)
      setNodes(nodesData.filter(n => n.node_type === "cc"))

      // Load sessions
      const { sessions: sessionsData, total: totalCount } = await apiClient.listSessions(
        token!,
        mosaicId,
        selectedNodeId === "all" ? undefined : parseInt(selectedNodeId),
        selectedStatus === "all" ? undefined : selectedStatus,
        false, // includeArchived - always false, user filters via status
        pageSize,
        (currentPage - 1) * pageSize
      )

      setSessions(sessionsData)
      setTotal(totalCount)
    } catch (error) {
      console.error("Failed to load data:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleViewSession = (sessionId: string) => {
    router.push(`/mosaic/${mosaicId}/chat?session=${sessionId}`)
  }

  const handleArchive = async (sessionId: string) => {
    if (!confirm("确定要归档这个会话吗？")) return

    try {
      await apiClient.archiveSession(sessionId, token!)
      await loadData()
    } catch (error) {
      console.error("Failed to archive session:", error)
      alert("归档失败")
    }
  }

  const handleUnarchive = async (sessionId: string) => {
    try {
      await apiClient.unarchiveSession(sessionId, token!)
      await loadData()
    } catch (error) {
      console.error("Failed to unarchive session:", error)
      alert("取消归档失败")
    }
  }

  const handleDelete = async (sessionId: string) => {
    if (!confirm("确定要删除这个会话吗？此操作无法撤销。")) return

    try {
      await apiClient.deleteSession(sessionId, token!)
      await loadData()
    } catch (error) {
      console.error("Failed to delete session:", error)
      alert("删除失败")
    }
  }

  // Filter sessions by search term
  const filteredSessions = sessions.filter(session =>
    session.session_id.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return <Badge variant="default">活跃</Badge>
      case "closed":
        return <Badge variant="secondary">已关闭</Badge>
      case "archived":
        return <Badge variant="outline">已归档</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getNodeName = (nodeId: number) => {
    const node = nodes.find(n => n.id === nodeId)
    return node?.node_id || `Node ${nodeId}`
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const days = Math.floor(hours / 24)

    if (hours < 1) return "刚刚"
    if (hours < 24) return `${hours}小时前`
    if (days < 7) return `${days}天前`
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">会话列表</h1>
          <p className="text-muted-foreground mt-1">
            管理和查看所有会话记录
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索会话 ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>

          <Select value={selectedNodeId} onValueChange={setSelectedNodeId}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="选择节点" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部节点</SelectItem>
              {nodes.map(node => (
                <SelectItem key={node.id} value={node.id.toString()}>
                  {node.node_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedStatus} onValueChange={setSelectedStatus}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="active">活跃</SelectItem>
              <SelectItem value="closed">已关闭</SelectItem>
              <SelectItem value="archived">已归档</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </Card>

      {/* Table */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <MessageSquare className="h-16 w-16 mb-4 opacity-30" />
            <p className="text-lg">暂无会话</p>
            <p className="text-sm mt-1">创建节点后可以开始新的会话</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-center">会话 ID</TableHead>
                <TableHead className="text-center">节点</TableHead>
                <TableHead className="text-center">状态</TableHead>
                <TableHead className="text-center">消息数</TableHead>
                <TableHead className="text-center">创建时间</TableHead>
                <TableHead className="text-center">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSessions.map(session => (
                <TableRow key={session.session_id}>
                  <TableCell className="text-center font-mono text-sm">
                    {session.session_id.slice(0, 8)}...
                  </TableCell>
                  <TableCell className="text-center">{getNodeName(session.node_id)}</TableCell>
                  <TableCell className="text-center">{getStatusBadge(session.status)}</TableCell>
                  <TableCell className="text-center">{session.message_count}</TableCell>
                  <TableCell className="text-center text-muted-foreground">
                    {formatDate(session.created_at)}
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewSession(session.session_id)}
                        title="查看会话"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>

                      {session.status === "archived" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleUnarchive(session.session_id)}
                          title="取消归档"
                        >
                          <ArchiveRestore className="h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleArchive(session.session_id)}
                          title="归档"
                        >
                          <Archive className="h-4 w-4" />
                        </Button>
                      )}

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(session.session_id)}
                        title="删除"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* Pagination */}
      {!loading && filteredSessions.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            共 {total} 条记录，第 {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, total)} 条
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              上一页
            </Button>
            <span className="text-sm">第 {currentPage} / {Math.ceil(total / pageSize)} 页</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(p => p + 1)}
              disabled={currentPage * pageSize >= total}
            >
              下一页
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
