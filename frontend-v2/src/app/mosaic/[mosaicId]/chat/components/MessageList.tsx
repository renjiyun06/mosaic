import { useRef, useEffect } from "react"
import { Loader2, MessageSquare } from "lucide-react"
import { MessageItem, type ParsedMessage } from "./MessageItem"

interface MessageListProps {
  messages: ParsedMessage[]
  collapsedMessages: Set<string>
  isLoading: boolean
  isVisible: boolean
  onToggleCollapse: (messageId: string) => void
}

export function MessageList({
  messages,
  collapsedMessages,
  isLoading,
  isVisible,
  onToggleCollapse,
}: MessageListProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const prevMessageCountRef = useRef<number>(0)
  const hasScrolledWithContentRef = useRef<boolean>(false)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    console.log('[MessageList] useEffect triggered', {
      isVisible,
      messagesLength: messages.length,
      prevMessageCount: prevMessageCountRef.current,
      hasScrolledWithContent: hasScrolledWithContentRef.current
    })

    // Only scroll when visible
    if (!isVisible) {
      console.log('[MessageList] Not visible, skipping scroll')
      return
    }

    const container = messagesContainerRef.current
    if (!container) {
      console.log('[MessageList] Container not found')
      return
    }

    const isAtBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 100

    console.log('[MessageList] Scroll check', {
      isAtBottom,
      scrollHeight: container.scrollHeight,
      scrollTop: container.scrollTop,
      clientHeight: container.clientHeight,
      shouldScroll: isAtBottom || messages.length > prevMessageCountRef.current
    })

    // Scroll to bottom only if user is near bottom AND there are new messages
    if (messages.length > prevMessageCountRef.current && isAtBottom) {
      // First time scroll with actual content: instant (no animation)
      // Subsequent scrolls: smooth animation
      // Note: Only count as "scrolled" if there are actual messages
      const behavior = (hasScrolledWithContentRef.current || messages.length === 0) ? "smooth" : "instant"
      console.log('[MessageList] Scrolling with behavior:', behavior)
      messagesEndRef.current?.scrollIntoView({ behavior })

      // Only mark as scrolled if we have actual messages
      if (messages.length > 0) {
        hasScrolledWithContentRef.current = true
      }
    }

    prevMessageCountRef.current = messages.length
  }, [messages, isVisible])

  return (
    <div
      ref={messagesContainerRef}
      className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6"
    >
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full text-muted-foreground">
          {isLoading ? (
            <div className="text-center">
              <Loader2 className="h-8 w-8 sm:h-10 sm:w-10 md:h-12 md:w-12 animate-spin mx-auto mb-2" />
              <p className="text-sm sm:text-base">正在加载消息...</p>
            </div>
          ) : (
            <div className="text-center">
              <MessageSquare className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
              <p className="text-sm sm:text-base">发送消息开始对话</p>
            </div>
          )}
        </div>
      ) : (
        <>
          {messages.map((msg) => (
            <MessageItem
              key={msg.message_id}
              message={msg}
              isCollapsed={collapsedMessages.has(msg.message_id)}
              onToggleCollapse={onToggleCollapse}
            />
          ))}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  )
}
