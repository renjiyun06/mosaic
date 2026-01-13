"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Loader2, MessageSquare } from "lucide-react"
import { apiClient } from "@/lib/api"
import { MessageItem, type ParsedMessage } from "@/components/message-item"
import { useAuth } from "@/contexts/auth-context"
import { MessageType } from "@/lib/types"

interface SessionViewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mosaicId: number
  sessionId: string | null
  nodeId?: string
}

export function SessionViewDialog({
  open,
  onOpenChange,
  mosaicId,
  sessionId,
  nodeId,
}: SessionViewDialogProps) {
  const { token } = useAuth()
  const [messages, setMessages] = useState<ParsedMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [collapsedMessages, setCollapsedMessages] = useState<Set<string>>(new Set())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Parse message payload
  const parseMessagePayload = useCallback((payload: any): any => {
    if (typeof payload === "string") {
      try {
        return JSON.parse(payload)
      } catch {
        return { message: payload }
      }
    }
    return payload
  }, [])

  // Load messages when dialog opens or sessionId changes
  useEffect(() => {
    if (!open || !sessionId || !token) {
      setMessages([])
      setError(null)
      setCollapsedMessages(new Set())
      return
    }

    const loadMessages = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch all messages for this session (use large page_size)
        const data = await apiClient.listMessages(mosaicId, {
          sessionId,
          nodeId,
          page: 1,
          pageSize: 1000,
        })

        // Parse message payload
        const parsedMessages: ParsedMessage[] = data.items.map((msg) => ({
          ...msg,
          contentParsed: parseMessagePayload(msg.payload),
        }))

        setMessages(parsedMessages)

        // Auto-collapse thinking, tool use, tool output, and system messages
        const toCollapse = new Set<string>()
        parsedMessages.forEach((msg) => {
          if (
            msg.message_type === MessageType.ASSISTANT_THINKING ||
            msg.message_type === MessageType.ASSISTANT_TOOL_USE ||
            msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT ||
            msg.message_type === MessageType.SYSTEM_MESSAGE
          ) {
            toCollapse.add(msg.message_id)
          }
        })
        setCollapsedMessages(toCollapse)

        // Scroll to bottom after messages load
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
        }, 100)
      } catch (err) {
        console.error("Failed to load messages:", err)
        setError(err instanceof Error ? err.message : "Failed to load messages")
        setMessages([])
      } finally {
        setLoading(false)
      }
    }

    loadMessages()
  }, [open, sessionId, nodeId, mosaicId, token, parseMessagePayload])

  const toggleThinkingCollapse = useCallback((messageId: string) => {
    setCollapsedMessages((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(messageId)) {
        newSet.delete(messageId)
      } else {
        newSet.add(messageId)
      }
      return newSet
    })
  }, [])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-base sm:text-lg">
            会话查看
            {sessionId && (
              <span className="ml-2 text-sm font-mono text-muted-foreground">
                {sessionId}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 py-2 border rounded-md bg-muted/20">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">加载消息中...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-destructive">
                <p className="text-sm">{error}</p>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-muted-foreground">
                <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p className="text-sm">该会话没有消息</p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageItem
                  key={msg.message_id}
                  message={msg}
                  isCollapsed={collapsedMessages.has(msg.message_id)}
                  onToggleCollapse={toggleThinkingCollapse}
                />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
