import { useState, useEffect, useRef, useCallback, memo } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Send, StopCircle, Mic, Circle, Loader2 } from "lucide-react"
import { useVoiceInput } from "@/hooks/use-voice-input"
import { apiClient } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

interface ChatInputProps {
  sessionId: string | null
  initialValue: string
  isLoading: boolean
  isConnected: boolean
  canSendMessage: boolean
  placeholder: string
  onSendMessage: (sessionId: string, message: string) => void
  onInterrupt: (sessionId: string) => void
  onInputChange: (sessionId: string, value: string) => void
}

// Convert markdown images to display format: ![🖼️ filename](url) -> [🖼️ filename]
function markdownToDisplay(markdown: string): string {
  return markdown.replace(/!\[([^\]]*)\]\([^\)]+\)/g, '[$1]')
}

// Convert display format back to markdown
function displayToMarkdown(display: string, originalMarkdown: string): string {
  // Extract all image markdown from original
  const imageMap = new Map<string, string>()
  const imageRegex = /!\[([^\]]*)\]\(([^\)]+)\)/g
  let match: RegExpExecArray | null

  while ((match = imageRegex.exec(originalMarkdown)) !== null) {
    const altText = match[1]
    const placeholder = `[${altText}]`
    imageMap.set(placeholder, match[0])
  }

  // Replace placeholders back to full markdown
  let result = display
  imageMap.forEach((fullMarkdown, placeholder) => {
    result = result.replaceAll(placeholder, fullMarkdown)
  })

  return result
}

// Map cursor position from display format to markdown format
function mapCursorPosition(cursorPos: number, displayValue: string, fullMarkdown: string): number {
  // Get the part before cursor in display
  const beforeDisplay = displayValue.substring(0, cursorPos)

  // Convert it to markdown
  const beforeMarkdown = displayToMarkdown(beforeDisplay, fullMarkdown)

  // The length of beforeMarkdown is the cursor position in fullMarkdown
  return beforeMarkdown.length
}

export const ChatInput = memo(function ChatInput({
  sessionId,
  initialValue,
  isLoading,
  isConnected,
  canSendMessage,
  placeholder,
  onSendMessage,
  onInterrupt,
  onInputChange,
}: ChatInputProps) {
  // fullMarkdown stores the complete markdown with full image URLs
  // displayValue is what shows in textarea (with simplified image placeholders)
  const [fullMarkdown, setFullMarkdown] = useState(initialValue)
  const [displayValue, setDisplayValue] = useState(() => markdownToDisplay(initialValue))
  const [isUploading, setIsUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const savedInputRef = useRef("")
  const { toast } = useToast()

  // Voice input hook
  const { isRecording, isSupported, interimText, finalText, start, stop } = useVoiceInput(
    (final, interim) => {
      // Update input with saved text + final + interim
      const newText = savedInputRef.current + final
      setFullMarkdown(newText)
      setDisplayValue(markdownToDisplay(newText))
      if (sessionId) {
        onInputChange(sessionId, newText)
      }
    },
    {
      lang: "zh-CN",
      onError: (error) => {
        console.error("Voice recognition error:", error)
      }
    }
  )

  // Sync with external changes (e.g., session switch or clear after send)
  useEffect(() => {
    setFullMarkdown(initialValue)
    setDisplayValue(markdownToDisplay(initialValue))
  }, [initialValue])

  // Auto-resize textarea based on content (optimized with direct DOM manipulation)
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = "auto"

    // Calculate new height (min 1 line, max 12 lines)
    const lineHeight = 24 // approximate line height
    const minHeight = lineHeight * 1 // 1 line for input
    const maxHeight = lineHeight * 12 // max 12 lines before scroll

    const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${newHeight}px`
  }, [displayValue])

  // Auto-focus textarea when loading finishes
  useEffect(() => {
    if (!isLoading && sessionId && isConnected && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isLoading, sessionId, isConnected])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newDisplayValue = e.target.value
    setDisplayValue(newDisplayValue)

    // Convert display format back to full markdown
    const newFullMarkdown = displayToMarkdown(newDisplayValue, fullMarkdown)
    setFullMarkdown(newFullMarkdown)

    if (sessionId) {
      onInputChange(sessionId, newFullMarkdown)
    }
  }, [sessionId, fullMarkdown, onInputChange])

  const handleSend = useCallback(() => {
    if (!fullMarkdown.trim() || !sessionId || !isConnected || !canSendMessage || isLoading) return

    // Stop voice recording if it's active
    if (isRecording) {
      stop()
    }

    // Send full markdown
    onSendMessage(sessionId, fullMarkdown)

    // Clear input
    setFullMarkdown("")
    setDisplayValue("")

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [fullMarkdown, sessionId, isConnected, canSendMessage, isLoading, isRecording, stop, onSendMessage])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleInterruptClick = useCallback(() => {
    if (sessionId) {
      onInterrupt(sessionId)
    }
  }, [sessionId, onInterrupt])

  // Handle voice input button click
  const handleVoiceClick = useCallback(async () => {
    if (isRecording) {
      stop()
    } else {
      // Save current input before starting recording
      savedInputRef.current = fullMarkdown
      await start()
    }
  }, [isRecording, fullMarkdown, start, stop])

  // Handle image upload
  const handleImageUpload = useCallback(async (file: File) => {
    if (!sessionId) return

    setIsUploading(true)
    try {
      const response = await apiClient.uploadImage(file)

      // Insert markdown image at cursor position
      const textarea = textareaRef.current
      if (textarea) {
        const cursorStart = textarea.selectionStart
        const cursorEnd = textarea.selectionEnd

        // Map display cursor positions to markdown positions
        const markdownStart = mapCursorPosition(cursorStart, displayValue, fullMarkdown)
        const markdownEnd = mapCursorPosition(cursorEnd, displayValue, fullMarkdown)

        // Create image markdown
        // Use first 8 characters of image_id as filename
        const imageIdPrefix = response.image_id.substring(0, 8)
        // Get file extension from original filename
        const fileExtension = response.filename.split('.').pop() || 'png'
        const displayName = `${imageIdPrefix}.${fileExtension}`
        const altText = `🖼️ ${displayName}`
        const imageMarkdown = `![${altText}](${response.url})`
        const imageDisplay = markdownToDisplay(imageMarkdown) // Should be [🖼️ filename]

        // Insert into fullMarkdown
        const beforeMarkdown = fullMarkdown.substring(0, markdownStart)
        const afterMarkdown = fullMarkdown.substring(markdownEnd)
        const newFullMarkdown = beforeMarkdown + imageMarkdown + afterMarkdown
        setFullMarkdown(newFullMarkdown)

        // Update display value
        const newDisplayValue = markdownToDisplay(newFullMarkdown)
        setDisplayValue(newDisplayValue)

        // Notify parent of change
        if (sessionId) {
          onInputChange(sessionId, newFullMarkdown)
        }

        // Set cursor position after inserted image (in display coordinates)
        setTimeout(() => {
          const newCursorPos = cursorStart + imageDisplay.length
          textarea.setSelectionRange(newCursorPos, newCursorPos)
          textarea.focus()
        }, 0)
      }

      // No toast notification - silent upload
    } catch (error) {
      console.error("Failed to upload image:", error)
      // Error toast is handled by apiClient
    } finally {
      setIsUploading(false)
    }
  }, [displayValue, fullMarkdown, sessionId, onInputChange])

  // Handle paste event
  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items
    if (!items) return

    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (file) {
          await handleImageUpload(file)
        }
        break
      }
    }
  }, [handleImageUpload])

  return (
    <div className="border-t bg-background">
      <div className="bg-background overflow-hidden">
        <Textarea
          ref={textareaRef}
          value={isRecording ? savedInputRef.current + finalText + interimText : displayValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={isRecording ? "🎤 Listening..." : isUploading ? "📤 Uploading image..." : placeholder}
          disabled={isLoading || !isConnected || !canSendMessage || isRecording || isUploading}
          className={`w-full resize-none overflow-y-auto border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 sm:px-3 pt-2 sm:pt-3 text-base ${isRecording || isUploading ? "opacity-70" : ""}`}
          style={{ minHeight: "24px" }}
        />
        <div className="flex justify-between items-center px-2 pb-2 gap-2">
          {/* Upload status indicator */}
          <div className="flex-1">
            {isUploading && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Uploading image...</span>
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            {/* Voice input button - only show if supported */}
            {isSupported && !isLoading && (
              <Button
                onClick={handleVoiceClick}
                variant={isRecording ? "destructive" : "outline"}
                size="icon"
                disabled={!isConnected || !canSendMessage || isUploading}
                className={isRecording ? "animate-pulse" : ""}
              >
                {isRecording ? (
                  <Circle className="h-4 w-4 fill-current" />
                ) : (
                  <Mic className="h-4 w-4" />
                )}
              </Button>
            )}

            {/* Send/Interrupt button */}
            {isLoading ? (
              <Button onClick={handleInterruptClick} variant="destructive" size="icon">
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSend}
                disabled={!fullMarkdown.trim() || !isConnected || !canSendMessage || isUploading}
                size="icon"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
})
