import { useState, useEffect, useRef, useCallback, memo } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Send, StopCircle, Mic, Circle } from "lucide-react"
import { useVoiceInput } from "@/hooks/use-voice-input"

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
  const [input, setInput] = useState(initialValue)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const savedInputRef = useRef("")

  // Voice input hook
  const { isRecording, isSupported, interimText, finalText, start, stop } = useVoiceInput(
    (final, interim) => {
      // Update input with saved text + final + interim
      const newInput = savedInputRef.current + final
      setInput(newInput)
      if (sessionId) {
        onInputChange(sessionId, newInput)
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
    setInput(initialValue)
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
  }, [input])

  // Auto-focus textarea when loading finishes
  useEffect(() => {
    if (!isLoading && sessionId && isConnected && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isLoading, sessionId, isConnected])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    setInput(value)
    if (sessionId) {
      onInputChange(sessionId, value)
    }
  }, [sessionId, onInputChange])

  const handleSend = useCallback(() => {
    if (!input.trim() || !sessionId || !isConnected || !canSendMessage || isLoading) return

    // Stop voice recording if it's active
    if (isRecording) {
      stop()
    }

    onSendMessage(sessionId, input)
    setInput("")

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [input, sessionId, isConnected, canSendMessage, isLoading, isRecording, stop, onSendMessage])

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
      savedInputRef.current = input
      await start()
    }
  }, [isRecording, input, start, stop])

  return (
    <div className="border-t bg-background">
      <div className="bg-background overflow-hidden">
        <Textarea
          ref={textareaRef}
          value={isRecording ? savedInputRef.current + finalText + interimText : input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={isRecording ? "🎤 Listening..." : placeholder}
          disabled={isLoading || !isConnected || !canSendMessage || isRecording}
          className={`w-full resize-none overflow-y-auto border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 sm:px-3 pt-2 sm:pt-3 text-base ${isRecording ? "opacity-70" : ""}`}
          style={{ minHeight: "24px" }}
        />
        <div className="flex justify-end px-2 pb-2 gap-2">
          {/* Voice input button - only show if supported */}
          {isSupported && !isLoading && (
            <Button
              onClick={handleVoiceClick}
              variant={isRecording ? "destructive" : "outline"}
              size="icon"
              disabled={!isConnected || !canSendMessage}
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
              disabled={!input.trim() || !isConnected || !canSendMessage}
              size="icon"
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
})
