"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Mail, Loader2, ChevronLeft, ChevronRight, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient } from "@/lib/api"
import type { MessageOut } from "@/lib/types"
import { MessageRole, MessageType } from "@/lib/types"

export default function MessagesPage() {
  const params = useParams()
  const mosaicId = parseInt(params.mosaicId as string)

  // Filter state
  const [sessionIdFilter, setSessionIdFilter] = useState("")

  // Data state
  const [messages, setMessages] = useState<MessageOut[]>([])
  const [loading, setLoading] = useState(false)

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)

  // Message detail dialog state
  const [selectedMessage, setSelectedMessage] = useState<MessageOut | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)

  // Fetch messages when sessionIdFilter or page changes
  useEffect(() => {
    if (!sessionIdFilter.trim()) {
      setMessages([])
      setTotal(0)
      setTotalPages(0)
      return
    }

    const fetchMessages = async () => {
      try {
        setLoading(true)
        const data = await apiClient.listMessages(mosaicId, {
          sessionId: sessionIdFilter.trim(),
          page: currentPage,
          pageSize,
        })
        setMessages(data.items)
        setTotal(data.total)
        setTotalPages(data.total_pages)
      } catch (error) {
        console.error("Failed to fetch messages:", error)
        setMessages([])
        setTotal(0)
        setTotalPages(0)
      } finally {
        setLoading(false)
      }
    }

    fetchMessages()
  }, [mosaicId, sessionIdFilter, currentPage, pageSize])

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

  const getRoleBadgeVariant = (role: MessageRole) => {
    switch (role) {
      case MessageRole.USER:
        return "default"
      case MessageRole.ASSISTANT:
        return "secondary"
      default:
        return "outline"
    }
  }

  const getRoleLabel = (role: MessageRole) => {
    switch (role) {
      case MessageRole.USER:
        return "用户"
      case MessageRole.ASSISTANT:
        return "助手"
      default:
        return role
    }
  }

  const getMessageTypeLabel = (type: MessageType) => {
    switch (type) {
      case MessageType.USER_MESSAGE:
        return "用户消息"
      case MessageType.ASSISTANT_TEXT:
        return "助手消息"
      case MessageType.ASSISTANT_THINKING:
        return "助手思考"
      case MessageType.ASSISTANT_TOOL_USE:
        return "工具调用"
      case MessageType.ASSISTANT_RESULT:
        return "助手结果"
      default:
        return type
    }
  }

  const handleViewDetail = (message: MessageOut) => {
    setSelectedMessage(message)
    setDetailDialogOpen(true)
  }

  const formatPayload = (payload: string) => {
    try {
      const parsed = typeof payload === "string" ? JSON.parse(payload) : payload
      if (parsed.text) {
        return parsed.text.substring(0, 100) + (parsed.text.length > 100 ? "..." : "")
      }
      if (parsed.content) {
        return JSON.stringify(parsed.content).substring(0, 100) + "..."
      }
      return JSON.stringify(parsed).substring(0, 100) + "..."
    } catch {
      return payload.substring(0, 100) + (payload.length > 100 ? "..." : "")
    }
  }

  return (
    <div className="flex flex-col h-full space-y-6 overflow-auto">
      {/* Header */}
      <div className="flex-shrink-0">
        <h1 className="text-3xl font-bold">会话消息</h1>
        <p className="text-muted-foreground mt-1">查看指定会话的所有消息记录，按序号升序排列</p>
      </div>

      {/* Filter */}
      <div className="flex-shrink-0 flex justify-end">
        <div className="relative w-1/2">
          <Input
            placeholder="输入会话 ID..."
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
      </div>

      {/* Message list */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !sessionIdFilter.trim() ? (
        <div className="flex-1 flex flex-col items-center pt-16 border rounded-lg">
          <Mail className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">输入会话 ID 开始查询</h2>
          <p className="text-muted-foreground text-center mb-6 max-w-lg">
            输入会话 ID 后，系统将自动加载该会话的所有消息记录。
          </p>
        </div>
      ) : messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center pt-16 border rounded-lg">
          <Mail className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">没有找到消息</h2>
          <p className="text-muted-foreground text-center mb-6 max-w-lg">
            该会话还没有任何消息记录，或会话 ID 不存在。
          </p>
        </div>
      ) : (
        <>
          <div className="flex-1 flex flex-col min-h-0 border rounded-lg">
            <div className="flex-1 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-center">序号</TableHead>
                    <TableHead className="text-center">角色</TableHead>
                    <TableHead className="text-center">消息类型</TableHead>
                    <TableHead className="text-center">内容预览</TableHead>
                    <TableHead className="text-center">创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {messages.map((message) => (
                    <TableRow key={message.id}>
                      <TableCell className="text-center">
                        <Badge variant="outline">{message.sequence}</Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={getRoleBadgeVariant(message.role)}>
                          {getRoleLabel(message.role)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{getMessageTypeLabel(message.message_type)}</Badge>
                      </TableCell>
                      <TableCell
                        className="max-w-md truncate text-sm text-muted-foreground cursor-pointer hover:text-foreground hover:underline"
                        onClick={() => handleViewDetail(message)}
                      >
                        {formatPayload(message.payload)}
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        {new Date(message.created_at).toLocaleString("zh-CN", {
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

      {/* Message Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-scroll" onOpenAutoFocus={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>消息详情</DialogTitle>
          </DialogHeader>
          {selectedMessage && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-1">序号</div>
                  <Badge variant="outline">{selectedMessage.sequence}</Badge>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-1">角色</div>
                  <Badge variant={getRoleBadgeVariant(selectedMessage.role)}>
                    {getRoleLabel(selectedMessage.role)}
                  </Badge>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-1">消息类型</div>
                  <Badge variant="outline">{getMessageTypeLabel(selectedMessage.message_type)}</Badge>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-1">创建时间</div>
                  <div className="text-sm">
                    {new Date(selectedMessage.created_at).toLocaleString("zh-CN", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                      hour12: false,
                    })}
                  </div>
                </div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground mb-2">消息内容</div>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto whitespace-pre-wrap break-words">
                  {typeof selectedMessage.payload === "string"
                    ? JSON.stringify(JSON.parse(selectedMessage.payload), null, 2)
                    : JSON.stringify(selectedMessage.payload, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
