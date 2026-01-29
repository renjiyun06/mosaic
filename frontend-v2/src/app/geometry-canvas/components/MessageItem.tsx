import { useCallback, memo, useState } from "react"
import { ChevronRight, ChevronDown, X } from "lucide-react"
import { MessageRole, MessageType, type MessageOut } from "@/lib/types"
import Image from "next/image"
import { Button } from "@/components/ui/button"

interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface MessageItemProps {
  message: ParsedMessage
  isCollapsed: boolean
  onToggleCollapse: (messageId: string) => void
}

// Parse message content to extract images
interface MessagePart {
  type: 'text' | 'image'
  content: string
}

function parseMessageContent(text: string): MessagePart[] {
  const parts: MessagePart[] = []
  // Match both formats: ![](url) and ![🖼️ filename](url)
  const imageRegex = /!\[([^\]]*)\]\((https?:\/\/[^\)]+)\)/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = imageRegex.exec(text)) !== null) {
    // Add text before image
    if (match.index > lastIndex) {
      const textContent = text.substring(lastIndex, match.index).trim()
      if (textContent) {
        parts.push({ type: 'text', content: textContent })
      }
    }

    // Add image (URL is in group 2)
    parts.push({ type: 'image', content: match[2] })
    lastIndex = imageRegex.lastIndex
  }

  // Add remaining text
  if (lastIndex < text.length) {
    const textContent = text.substring(lastIndex).trim()
    if (textContent) {
      parts.push({ type: 'text', content: textContent })
    }
  }

  // If no parts were added, return original text as single text part
  if (parts.length === 0 && text.trim()) {
    parts.push({ type: 'text', content: text })
  }

  return parts
}

// Image lightbox component
function ImageLightbox({ imageUrl, onClose }: { imageUrl: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-4 right-4 text-white hover:bg-white/20"
        onClick={onClose}
      >
        <X className="h-6 w-6" />
      </Button>
      <div className="relative max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <Image
          src={imageUrl}
          alt="Full size image"
          width={1200}
          height={1200}
          className="object-contain max-w-full max-h-[90vh]"
          unoptimized
        />
      </div>
    </div>
  )
}

export const MessageItem = memo(function MessageItem({
  message: msg,
  isCollapsed,
  onToggleCollapse,
}: MessageItemProps) {
  const [lightboxImage, setLightboxImage] = useState<string | null>(null)

  // Don't render assistant_result messages (stats shown in header)
  if (msg.message_type === MessageType.ASSISTANT_RESULT) {
    return null
  }

  const isUser = msg.role === MessageRole.USER
  const isThinking = msg.message_type === MessageType.ASSISTANT_THINKING
  const isSystemMessage = msg.message_type === MessageType.SYSTEM_MESSAGE
  const isToolUse = msg.message_type === MessageType.ASSISTANT_TOOL_USE
  const isToolOutput = msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT
  const isPreCompact = msg.message_type === MessageType.ASSISTANT_PRE_COMPACT
  const isCollapsible = isThinking || isSystemMessage || isToolUse || isToolOutput || isPreCompact

  const handleToggle = useCallback(() => {
    onToggleCollapse(msg.message_id)
  }, [msg.message_id, onToggleCollapse])

  // Render message content with images
  const renderMessageContent = (content: string) => {
    const parts = parseMessageContent(content)

    return (
      <div className="space-y-2">
        {parts.map((part, index) => {
          if (part.type === 'text') {
            return (
              <div key={index} className="whitespace-pre-wrap break-words">
                {part.content}
              </div>
            )
          } else {
            return (
              <div key={index} className="my-2">
                <Image
                  src={part.content}
                  alt="Uploaded image"
                  width={300}
                  height={300}
                  className="rounded cursor-pointer hover:opacity-90 transition-opacity max-w-full h-auto"
                  onClick={() => setLightboxImage(part.content)}
                  unoptimized
                />
              </div>
            )
          }
        })}
      </div>
    )
  }

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 sm:mb-4`}
    >
      <div
        className={`max-w-[85%] sm:max-w-[80%] md:max-w-[70%] rounded-lg ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        } ${isCollapsible ? "px-2 py-1" : "px-3 sm:px-4 py-2"}`}
      >
        {isThinking ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">💭 思考中...</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm px-2 pb-1 pt-0">
                {renderMessageContent(msg.contentParsed.message)}
              </div>
            )}
          </div>
        ) : isSystemMessage ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">🔔 系统消息</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm px-2 pb-1 pt-0">
                {renderMessageContent(msg.contentParsed.message)}
              </div>
            )}
          </div>
        ) : isToolUse ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">🔧 {msg.contentParsed.tool_name}</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0 font-mono">
                {JSON.stringify(msg.contentParsed.tool_input, null, 2)}
              </div>
            )}
          </div>
        ) : isToolOutput ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">
                📤 {msg.contentParsed?.tool_name || 'Tool'} 结果
                {(msg.contentParsed?.tool_output === null || msg.contentParsed?.tool_output === undefined) && (
                  <span className="ml-1 text-xs opacity-50">(空)</span>
                )}
              </span>
            </div>
            {!isCollapsed && (
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0 font-mono">
                {(() => {
                  const output = msg.contentParsed?.tool_output
                  if (output === undefined || output === null) {
                    return <span className="text-muted-foreground italic">工具执行完成，无返回输出</span>
                  }
                  if (typeof output === 'string') {
                    return output.trim() || <span className="text-muted-foreground italic">空字符串</span>
                  }
                  return JSON.stringify(output, null, 2)
                })()}
              </div>
            )}
          </div>
        ) : isPreCompact ? (
          <div>
            <div
              className="flex items-center gap-1 cursor-pointer hover:opacity-80 px-2 py-1"
              onClick={handleToggle}
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3 opacity-70" />
              ) : (
                <ChevronDown className="h-3 w-3 opacity-70" />
              )}
              <span className="text-xs opacity-70">🗜️ 上下文压缩</span>
            </div>
            {!isCollapsed && (
              <div className="text-sm px-2 pb-1 pt-0 text-muted-foreground italic">
                会话上下文即将被压缩以节省 token 使用
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm">
            {renderMessageContent(msg.contentParsed.message)}
          </div>
        )}
      </div>

      {/* Image lightbox */}
      {lightboxImage && (
        <ImageLightbox imageUrl={lightboxImage} onClose={() => setLightboxImage(null)} />
      )}
    </div>
  )
})

export type { ParsedMessage }
