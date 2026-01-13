import { useCallback, memo } from "react"
import { ChevronRight, ChevronDown } from "lucide-react"
import { MessageRole, MessageType, type MessageOut } from "@/lib/types"

interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface MessageItemProps {
  message: ParsedMessage
  isCollapsed: boolean
  onToggleCollapse: (messageId: string) => void
}

export const MessageItem = memo(function MessageItem({
  message: msg,
  isCollapsed,
  onToggleCollapse,
}: MessageItemProps) {
  // Don't render assistant_result messages (stats shown in header)
  if (msg.message_type === MessageType.ASSISTANT_RESULT) {
    return null
  }

  const isUser = msg.role === MessageRole.USER
  const isThinking = msg.message_type === MessageType.ASSISTANT_THINKING
  const isSystemMessage = msg.message_type === MessageType.SYSTEM_MESSAGE
  const isToolUse = msg.message_type === MessageType.ASSISTANT_TOOL_USE
  const isToolOutput = msg.message_type === MessageType.ASSISTANT_TOOL_OUTPUT
  const isCollapsible = isThinking || isSystemMessage || isToolUse || isToolOutput

  const handleToggle = useCallback(() => {
    onToggleCollapse(msg.message_id)
  }, [msg.message_id, onToggleCollapse])

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
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0">
                {msg.contentParsed.message}
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
              <div className="text-sm whitespace-pre-wrap break-words px-2 pb-1 pt-0">
                {msg.contentParsed.message}
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
        ) : (
          <div className="text-sm whitespace-pre-wrap break-words">
            {msg.contentParsed.message}
          </div>
        )}
      </div>
    </div>
  )
})

export type { ParsedMessage }
