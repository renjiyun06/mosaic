import { useRef, useEffect } from "react"
import { Loader2, MessageSquare } from "lucide-react"
import { MessageItem, type ParsedMessage } from "./MessageItem"
import { MessageRole } from "@/lib/types"

interface MessageListProps {
  messages: ParsedMessage[]
  collapsedMessages: Set<string>
  isLoading: boolean
  isVisible: boolean
  onToggleCollapse: (messageId: string) => void
  sessionId: string
  onScrollStateChange?: (state: { scrollTop: number; autoScrollEnabled: boolean }) => void
  initialScrollState?: { scrollTop: number; autoScrollEnabled: boolean }
}

export function MessageList({
  messages,
  collapsedMessages,
  isLoading,
  isVisible,
  onToggleCollapse,
  sessionId,
  onScrollStateChange,
  initialScrollState,
}: MessageListProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const prevMessageCountRef = useRef<number>(0)
  const autoScrollEnabledRef = useRef<boolean>(initialScrollState?.autoScrollEnabled ?? true)
  const isRestoringRef = useRef<boolean>(false)

  // Monitor user scroll behavior to update auto-scroll state
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return

    const handleScroll = () => {
      const isNearBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < 100

      // Enable auto-scroll when user scrolls near bottom, disable when scrolling up
      autoScrollEnabledRef.current = isNearBottom

      // Save scroll state (skip during restoration)
      if (!isRestoringRef.current && onScrollStateChange) {
        onScrollStateChange({
          scrollTop: container.scrollTop,
          autoScrollEnabled: isNearBottom
        })
      }
    }

    container.addEventListener("scroll", handleScroll)
    return () => container.removeEventListener("scroll", handleScroll)
  }, [onScrollStateChange])

  // Restore scroll position when session becomes visible
  useEffect(() => {
    if (!isVisible || !messagesContainerRef.current) return

    const container = messagesContainerRef.current

    // Delay restoration to ensure DOM is rendered
    requestAnimationFrame(() => {
      isRestoringRef.current = true

      if (initialScrollState) {
        if (initialScrollState.autoScrollEnabled) {
          // Was at bottom, scroll to new bottom
          container.scrollTop = container.scrollHeight
        } else {
          // Was in middle, restore to original position
          container.scrollTop = initialScrollState.scrollTop
        }
      }

      // Allow state saving after restoration completes
      setTimeout(() => {
        isRestoringRef.current = false
      }, 100)
    })
  }, [isVisible, sessionId])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (!isVisible) return

    const container = messagesContainerRef.current
    if (!container) return

    // Check if there are new messages
    if (messages.length > prevMessageCountRef.current) {
      // Get the latest message
      const latestMessage = messages[messages.length - 1]

      // If user sent a message, force scroll to bottom and enable auto-scroll
      if (latestMessage && latestMessage.role === MessageRole.USER) {
        autoScrollEnabledRef.current = true
        requestAnimationFrame(() => {
          container.scrollTop = container.scrollHeight
          // Update scroll state
          if (onScrollStateChange) {
            onScrollStateChange({
              scrollTop: container.scrollHeight,
              autoScrollEnabled: true
            })
          }
        })
      } else if (autoScrollEnabledRef.current) {
        // For non-user messages, only scroll if auto-scroll is enabled
        requestAnimationFrame(() => {
          container.scrollTop = container.scrollHeight
        })
      }
    }

    prevMessageCountRef.current = messages.length
  }, [messages, isVisible, onScrollStateChange])

  return (
    <div
      ref={messagesContainerRef}
      className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6"
      style={{
        scrollbarWidth: 'thin',
        scrollbarColor: 'hsl(var(--border)) transparent'
      }}
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
