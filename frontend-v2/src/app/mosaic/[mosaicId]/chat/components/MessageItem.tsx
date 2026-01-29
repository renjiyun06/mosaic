import { useCallback, memo, useState, useRef } from "react"
import { ChevronRight, ChevronDown, X, Code2, FileText, Copy, Check } from "lucide-react"
import { MessageRole, MessageType, type MessageOut } from "@/lib/types"
import Image from "next/image"
import { Button } from "@/components/ui/button"
import { useTheme } from "@/contexts/theme-context"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import rehypeRaw from "rehype-raw"
import "highlight.js/styles/github-dark.css"

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
  const { theme } = useTheme()
  const [lightboxImage, setLightboxImage] = useState<string | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const [copiedCode, setCopiedCode] = useState<string | null>(null)

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

  // Handle code copy
  const handleCopyCode = useCallback(async (code: string, blockId: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedCode(blockId)
      setTimeout(() => setCopiedCode(null), 2000)
    } catch (error) {
      console.error("Failed to copy code:", error)
    }
  }, [])

  // Get theme-specific classes for message bubble
  const getMessageBubbleClasses = () => {
    const baseClasses = "max-w-[85%] sm:max-w-[80%] md:max-w-[70%] rounded-lg"
    const paddingClasses = isCollapsible ? "px-2 py-1" : "px-3 sm:px-4 py-2"

    let themeClasses = ""

    if (isUser) {
      // User message bubble
      switch (theme) {
        case 'cyberpunk':
          themeClasses = "bg-primary text-primary-foreground neon-border shadow-[0_0_12px_hsl(var(--primary)/0.4)]"
          break
        case 'glassmorphism':
          themeClasses = "glass-card text-foreground border border-border/50"
          break
        case 'terminal':
          themeClasses = "bg-black text-primary border border-primary font-mono"
          break
        case 'minimal':
          themeClasses = "bg-foreground text-background border border-foreground"
          break
        default:
          themeClasses = "bg-muted"
      }
    } else {
      // Assistant message bubble
      switch (theme) {
        case 'cyberpunk':
          themeClasses = "bg-card/50 border border-primary/30 shadow-[0_0_8px_hsl(var(--primary)/0.2)]"
          break
        case 'glassmorphism':
          themeClasses = "glass-card border border-border/50"
          break
        case 'terminal':
          themeClasses = "bg-black/80 border border-primary/50 font-mono"
          break
        case 'minimal':
          themeClasses = "bg-background border-2 border-foreground/20"
          break
        default:
          themeClasses = "bg-muted"
      }
    }

    return `${baseClasses} ${themeClasses} ${paddingClasses}`
  }

  // Render message content with images and markdown
  const renderMessageContent = (content: string) => {
    const parts = parseMessageContent(content)

    // Raw text mode - show original content
    if (showRaw) {
      return (
        <div className="space-y-2">
          {parts.map((part, index) => {
            if (part.type === 'text') {
              return (
                <div key={index} className="whitespace-pre-wrap break-words font-mono text-xs bg-muted/30 p-2 rounded">
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

    // Markdown rendering mode
    return (
      <div className="space-y-2">
        {parts.map((part, index) => {
          if (part.type === 'text') {
            return (
              <div key={index} className="markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight, rehypeRaw]}
                  components={{
                    // Custom code block with copy button
                    code({ node, inline, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '')
                      const language = match ? match[1] : ''
                      const blockId = `${msg.message_id}-${index}-${language}`

                      // Extract text content recursively
                      const extractCodeText = (node: any): string => {
                        if (typeof node === 'string') return node
                        if (typeof node === 'number') return String(node)
                        if (Array.isArray(node)) return node.map(extractCodeText).join('')
                        if (node && typeof node === 'object' && node.props) {
                          return extractCodeText(node.props.children)
                        }
                        return ''
                      }

                      const code = extractCodeText(children).replace(/\n$/, '')

                      // More robust check for code blocks vs inline code
                      // Code blocks: explicitly marked as !inline OR has a language class
                      // Inline code: explicitly marked as inline OR no language class
                      const isCodeBlock = inline === false || (inline !== true && className && /language-/.test(className))

                      if (isCodeBlock && code) {
                        const handleCopyCodeBlock = (e: React.MouseEvent) => {
                          e.stopPropagation()
                          e.preventDefault()

                          // Try to extract text from the DOM element
                          const button = e.currentTarget as HTMLElement
                          const codeBlock = button.closest('.relative')?.querySelector('code')

                          if (codeBlock) {
                            const text = codeBlock.innerText || codeBlock.textContent || code
                            handleCopyCode(text, blockId)
                          } else {
                            handleCopyCode(code, blockId)
                          }
                        }

                        return (
                          <div className="relative group my-2" data-code-block={blockId}>
                            <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0 bg-background/80 backdrop-blur hover:bg-background/90"
                                onClick={handleCopyCodeBlock}
                                title={copiedCode === blockId ? "Copied!" : "Copy code"}
                              >
                                {copiedCode === blockId ? (
                                  <Check className="h-3.5 w-3.5" />
                                ) : (
                                  <Copy className="h-3.5 w-3.5" />
                                )}
                              </Button>
                            </div>
                            {language && (
                              <div className="absolute left-3 top-2 text-xs text-muted-foreground opacity-60 z-10 pointer-events-none">
                                {language}
                              </div>
                            )}
                            <pre className={`${className} ${language ? 'pt-8' : ''}`}>
                              <code className={className} {...props}>
                                {children}
                              </code>
                            </pre>
                          </div>
                        )
                      }

                      // Inline code - prevent line breaks with stronger constraints
                      return (
                        <code
                          className="inline-code-no-wrap"
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    },
                    // Custom styling for other elements (no copy functionality)
                    p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                    li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                    h1: ({ children }) => <h1 className="text-2xl font-bold mb-2 mt-4">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-xl font-bold mb-2 mt-3">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-lg font-bold mb-2 mt-2">{children}</h3>,
                    h4: ({ children }) => <h4 className="text-base font-bold mb-2 mt-2">{children}</h4>,
                    h5: ({ children }) => <h5 className="text-sm font-bold mb-2 mt-2">{children}</h5>,
                    h6: ({ children }) => <h6 className="text-sm font-bold mb-2 mt-2">{children}</h6>,
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-primary pl-4 italic my-2">{children}</blockquote>
                    ),
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-2">
                        <table className="min-w-full border border-border">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="border border-border px-3 py-2 bg-muted font-semibold text-left">{children}</th>
                    ),
                    td: ({ children }) => (
                      <td className="border border-border px-3 py-2">{children}</td>
                    ),
                    a: ({ children, href }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {part.content}
                </ReactMarkdown>
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
      <div className={`relative group ${getMessageBubbleClasses()}`}>
        {/* Toggle raw/rendered view button - Only show for non-collapsible messages */}
        {!isCollapsible && (
          <div className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 bg-background/90 backdrop-blur border shadow-sm"
              onClick={() => setShowRaw(!showRaw)}
              title={showRaw ? "Show rendered view" : "Show raw text"}
            >
              {showRaw ? (
                <FileText className="h-3 w-3" />
              ) : (
                <Code2 className="h-3 w-3" />
              )}
            </Button>
          </div>
        )}
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
