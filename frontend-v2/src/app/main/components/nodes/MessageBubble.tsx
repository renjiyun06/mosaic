/**
 * Message Bubble Component - Dual-theme message rendering with Lucide icons
 * UX Best Practices:
 * - No emoji icons (use SVG from Lucide React)
 * - Color + Icon (accessibility: not color alone)
 * - ARIA labels for interactive elements
 * - Cursor pointer on clickable elements
 * - Smooth transitions (200ms)
 * - Text Scrim for readability in Apple Glass theme
 */

import { useState, useCallback, memo } from "react"
import { motion } from "framer-motion"
import {
  Brain,
  Bell,
  Wrench,
  FileOutput,
  Minimize2,
  ChevronRight,
  ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { MessageType, type MessageOut } from "@/lib/types"
import { useTheme } from "../../hooks/useTheme"

// Parsed message type
interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface MessageBubbleProps {
  message: ParsedMessage
  onToggleCollapse?: (messageId: string) => void
  isCollapsed?: boolean
}

// Message type icon configuration (Dual-theme support)
// Note: Tailwind classes are used here for Cyberpunk theme
// Apple Glass theme uses CSS variables dynamically
const MESSAGE_ICON_CONFIG = {
  [MessageType.ASSISTANT_THINKING]: {
    Icon: Brain,
    color: "text-cyan-400", // Cyberpunk
    bgColor: "bg-cyan-500/15", // Cyberpunk
    borderColor: "border-cyan-400/30", // Cyberpunk
    glowColor: "shadow-[0_0_20px_rgba(34,211,238,0.4)]", // Cyberpunk
    label: "Thinking...",
  },
  [MessageType.SYSTEM_MESSAGE]: {
    Icon: Bell,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/40",
    borderColor: "border-yellow-400/50",
    glowColor: "shadow-[0_0_20px_rgba(250,204,21,0.4)]",
    label: "System",
  },
  [MessageType.ASSISTANT_TOOL_USE]: {
    Icon: Wrench,
    color: "text-green-400",
    bgColor: "bg-green-500/15",
    borderColor: "border-green-400/30",
    glowColor: "shadow-[0_0_20px_rgba(0,255,0,0.4)]",
    label: (toolName?: string) => toolName || "Tool",
  },
  [MessageType.ASSISTANT_TOOL_OUTPUT]: {
    Icon: FileOutput,
    color: "text-cyan-300",
    bgColor: "bg-cyan-500/15",
    borderColor: "border-cyan-400/30",
    glowColor: "shadow-[0_0_20px_rgba(34,211,238,0.4)]",
    label: (toolName?: string) => `${toolName || "Tool"} Output`,
  },
  [MessageType.ASSISTANT_PRE_COMPACT]: {
    Icon: Minimize2,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/15",
    borderColor: "border-yellow-400/30",
    glowColor: "shadow-[0_0_20px_rgba(250,204,21,0.4)]",
    label: "Compacting...",
  },
}

/**
 * Performance optimization: Memoize component to prevent re-renders when props don't change
 * This is critical when there are many messages (50+) in the list
 */
export const MessageBubble = memo(function MessageBubble({ message, onToggleCollapse, isCollapsed = false }: MessageBubbleProps) {
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'
  const isUser = message.role === "user"
  const isCollapsibleType =
    message.message_type === MessageType.ASSISTANT_THINKING ||
    message.message_type === MessageType.SYSTEM_MESSAGE ||
    message.message_type === MessageType.ASSISTANT_TOOL_USE ||
    message.message_type === MessageType.ASSISTANT_TOOL_OUTPUT ||
    message.message_type === MessageType.ASSISTANT_PRE_COMPACT

  // Get icon config for collapsible messages
  const iconConfig = isCollapsibleType
    ? MESSAGE_ICON_CONFIG[message.message_type]
    : null

  // Extract message content
  const messageContent =
    message.contentParsed?.message || JSON.stringify(message.contentParsed)

  // Get tool name for tool messages
  const toolName = message.contentParsed?.tool_name

  // Handle collapse toggle
  const handleToggle = useCallback(() => {
    if (onToggleCollapse) {
      onToggleCollapse(message.message_id)
    }
  }, [message.message_id, onToggleCollapse])

  // User or Assistant message (not collapsible)
  if (!isCollapsibleType) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className={cn("nodrag flex", isUser ? "justify-end" : "justify-start")}
      >
        <div
          className={cn(
            "max-w-[75%] rounded-xl border p-3 transition-all duration-200",
            // Cyberpunk theme - Tailwind classes
            !isAppleGlass && [
              isUser
                ? "border-cyan-400/30 bg-cyan-500/20 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)] backdrop-blur-xl"
                : "border-white/10 bg-slate-800/50 hover:border-white/20 backdrop-blur-xl",
            ]
          )}
          style={
            isAppleGlass
              ? {
                  // Apple Glass theme - CSS variables
                  ...(isUser
                    ? {
                        // User message: Blue-500 15% (stronger contrast than 3%)
                        background: "rgba(59, 130, 246, 0.15)",
                        borderColor: "var(--glass-border)",
                        boxShadow: "var(--shadow-glass)",
                        backdropFilter: "blur(5px) saturate(105%)",
                      }
                    : {
                        // Assistant message: 3% ultra-thin glass
                        background: "var(--glass-background)",
                        backdropFilter: "var(--backdrop-blur)",
                        borderColor: "var(--glass-border)",
                        boxShadow: "var(--shadow-glass)",
                      }),
                }
              : undefined
          }
        >
          {/* Message content with Text Scrim for Apple Glass */}
          <p
            className={cn(
              "text-xs whitespace-pre-wrap break-words leading-relaxed select-text cursor-text",
              // Cyberpunk: direct text color
              !isAppleGlass && "text-white"
            )}
            style={
              isAppleGlass
                ? {
                    // Apple Glass: Text Scrim for readability
                    color: "var(--color-text-primary)",
                    background: "var(--text-scrim-content-bg)",
                    backdropFilter: "var(--text-scrim-content-blur)",
                    border: "var(--text-scrim-content-border)",
                    borderRadius: "var(--text-scrim-content-radius)",
                    padding: "var(--text-scrim-content-padding)",
                    boxShadow: "var(--shadow-textScrim)",
                  }
                : undefined
            }
          >
            {messageContent}
          </p>
        </div>
      </motion.div>
    )
  }

  // Collapsible message (thinking, tool, system)
  if (!iconConfig) return null

  const Icon = iconConfig.Icon
  const label =
    typeof iconConfig.label === "function" ? iconConfig.label(toolName) : iconConfig.label

  if (isCollapsed) {
    // Collapsed state: compact view with subtle border (no glow - intentionally de-emphasized)
    return (
      <div className="nodrag flex justify-start">
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
          className={cn(
            "group flex items-center gap-2 rounded-lg px-3 py-1.5 border",
            "transition-all duration-200",
            // UX: Cursor pointer on clickable
            "cursor-pointer",
            // Cyberpunk theme - Tailwind classes
            !isAppleGlass && [iconConfig.bgColor, iconConfig.borderColor, "hover:bg-opacity-30"]
          )}
          style={
            isAppleGlass
              ? {
                  // Apple Glass: 3% glass background with theme border
                  background: "var(--glass-background)",
                  backdropFilter: "var(--backdrop-blur)",
                  borderColor: "var(--glass-border)",
                  boxShadow: "var(--shadow-glass)",
                }
              : undefined
          }
          onClick={handleToggle}
          role="button"
          tabIndex={0}
          aria-label={`Expand ${label} message`}
          aria-expanded="false"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault()
              handleToggle()
            }
          }}
        >
          {/* Chevron icon */}
          <ChevronRight
            className={cn("h-3.5 w-3.5 shrink-0", !isAppleGlass && iconConfig.color)}
            style={isAppleGlass ? { color: "var(--color-primary)" } : undefined}
          />

          {/* Message type icon (UX: icon + text for accessibility) */}
          <Icon
            className={cn("h-3.5 w-3.5 shrink-0", !isAppleGlass && iconConfig.color)}
            style={isAppleGlass ? { color: "var(--color-primary)" } : undefined}
          />

          {/* Label text */}
          <span
            className={cn("text-xs font-mono leading-none", !isAppleGlass && iconConfig.color)}
            style={isAppleGlass ? { color: "var(--color-text-primary)" } : undefined}
          >
            {label}
          </span>
        </motion.div>
      </div>
    )
  }

  // Expanded state: full content with subtle border (no glow - intentionally de-emphasized)
  return (
    <div className="nodrag flex justify-start">
      <motion.div
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15 }}
        className={cn(
          "rounded-lg w-full border",
          // Cyberpunk theme - Tailwind classes
          !isAppleGlass && [iconConfig.bgColor, iconConfig.borderColor]
        )}
        style={
          isAppleGlass
            ? {
                // Apple Glass: 3% glass background
                background: "var(--glass-background)",
                backdropFilter: "var(--backdrop-blur)",
                borderColor: "var(--glass-border)",
                boxShadow: "var(--shadow-glass)",
              }
            : undefined
        }
      >
      {/* Header (clickable to collapse) */}
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2",
          // UX: Cursor pointer
          "cursor-pointer",
          // UX: Subtle hover feedback
          "transition-colors duration-200 rounded-t-lg",
          !isAppleGlass && "hover:bg-white/5"
        )}
        style={
          isAppleGlass
            ? {
                // Apple Glass: subtle hover with glass effect
                transition: "background-color 200ms",
              }
            : undefined
        }
        onMouseEnter={(e) => {
          if (isAppleGlass) {
            e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)"
          }
        }}
        onMouseLeave={(e) => {
          if (isAppleGlass) {
            e.currentTarget.style.background = "transparent"
          }
        }}
        onClick={handleToggle}
        role="button"
        tabIndex={0}
        aria-label={`Collapse ${label} message`}
        aria-expanded="true"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            handleToggle()
          }
        }}
      >
        {/* Chevron icon (down when expanded) */}
        <ChevronDown
          className={cn("h-3.5 w-3.5 shrink-0", !isAppleGlass && iconConfig.color)}
          style={isAppleGlass ? { color: "var(--color-primary)" } : undefined}
        />

        {/* Message type icon */}
        <Icon
          className={cn("h-3.5 w-3.5 shrink-0", !isAppleGlass && iconConfig.color)}
          style={isAppleGlass ? { color: "var(--color-primary)" } : undefined}
        />

        {/* Label text */}
        <span
          className={cn("text-xs font-mono leading-none", !isAppleGlass && iconConfig.color)}
          style={isAppleGlass ? { color: "var(--color-text-primary)" } : undefined}
        >
          {label}
        </span>
      </div>

      {/* Content - subtle padding, no extra borders */}
      <div className="px-3 py-2 select-text cursor-text">
        {message.message_type === MessageType.ASSISTANT_TOOL_USE ? (
          // Tool use: show JSON formatted
          <pre
            className={cn(
              "text-xs font-mono whitespace-pre-wrap break-words leading-relaxed overflow-x-hidden",
              !isAppleGlass && "text-slate-200"
            )}
            style={isAppleGlass ? { color: "var(--color-text-primary)" } : undefined}
          >
            {JSON.stringify(message.contentParsed?.tool_input, null, 2)}
          </pre>
        ) : message.message_type === MessageType.ASSISTANT_TOOL_OUTPUT ? (
          // Tool output: handle null/empty
          <div
            className={cn(
              "text-xs font-mono whitespace-pre-wrap break-words leading-relaxed",
              !isAppleGlass && "text-slate-200"
            )}
            style={isAppleGlass ? { color: "var(--color-text-primary)" } : undefined}
          >
            {(() => {
              const output = message.contentParsed?.tool_output
              if (output === undefined || output === null) {
                return (
                  <span
                    className={!isAppleGlass ? "text-slate-400 italic" : "italic"}
                    style={isAppleGlass ? { color: "var(--color-text-muted)" } : undefined}
                  >
                    Tool executed, no output
                  </span>
                )
              }
              if (typeof output === "string") {
                return (
                  output.trim() || (
                    <span
                      className={!isAppleGlass ? "text-slate-400 italic" : "italic"}
                      style={isAppleGlass ? { color: "var(--color-text-muted)" } : undefined}
                    >
                      Empty string
                    </span>
                  )
                )
              }
              return <pre className="whitespace-pre-wrap break-words overflow-x-hidden">{JSON.stringify(output, null, 2)}</pre>
            })()}
          </div>
        ) : message.message_type === MessageType.ASSISTANT_PRE_COMPACT ? (
          // Pre-compact: info message
          <p
            className={cn("text-xs italic", !isAppleGlass && "text-slate-300")}
            style={isAppleGlass ? { color: "var(--color-text-secondary)" } : undefined}
          >
            Session context will be compacted to save tokens
          </p>
        ) : (
          // Default: message content (includes system messages)
          <p
            className={cn(
              "text-xs font-mono whitespace-pre-wrap break-words leading-relaxed",
              !isAppleGlass && "text-slate-200"
            )}
            style={isAppleGlass ? { color: "var(--color-text-primary)" } : undefined}
          >
            {messageContent}
          </p>
        )}
      </div>
    </motion.div>
    </div>
  )
})
