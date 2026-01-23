/**
 * Message Bubble Component - Cyberpunk style message rendering with Lucide icons
 * UX Best Practices:
 * - No emoji icons (use SVG from Lucide React)
 * - Color + Icon (accessibility: not color alone)
 * - ARIA labels for interactive elements
 * - Cursor pointer on clickable elements
 * - Smooth transitions (200ms)
 */

import { useState, useCallback } from "react"
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

// Parsed message type
interface ParsedMessage extends MessageOut {
  contentParsed: any
}

interface MessageBubbleProps {
  message: ParsedMessage
  onToggleCollapse?: (messageId: string) => void
  isCollapsed?: boolean
}

// Message type icon configuration (Cyberpunk style - enhanced visibility)
const MESSAGE_ICON_CONFIG = {
  [MessageType.ASSISTANT_THINKING]: {
    Icon: Brain,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/15",
    borderColor: "border-cyan-400/30",
    glowColor: "shadow-[0_0_20px_rgba(34,211,238,0.4)]",
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

export function MessageBubble({ message, onToggleCollapse, isCollapsed = false }: MessageBubbleProps) {
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
            "max-w-[75%] rounded-xl border p-3 backdrop-blur-xl transition-all duration-200",
            isUser
              ? cn(
                  // User message: Cyan neon (Cyberpunk primary color)
                  "border-cyan-400/30 bg-cyan-500/20",
                  "hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
                )
              : cn(
                  // Assistant message: Dark glass
                  "border-white/10 bg-slate-800/50",
                  "hover:border-white/20"
                )
          )}
        >
          {/* Message content only - no role label, no timestamp (UX: clean and minimal) */}
          <p className="text-xs text-white whitespace-pre-wrap break-words leading-relaxed select-text cursor-text">
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
            // Subtle styling: background + border (no glow - de-emphasized)
            iconConfig.bgColor,
            iconConfig.borderColor,
            // UX: Cursor pointer on clickable
            "cursor-pointer",
            // UX: Enhanced background on hover
            "hover:bg-opacity-30"
          )}
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
          <ChevronRight className={cn("h-3.5 w-3.5 shrink-0", iconConfig.color)} />

          {/* Message type icon (UX: icon + text for accessibility) */}
          <Icon className={cn("h-3.5 w-3.5 shrink-0", iconConfig.color)} />

          {/* Label text */}
          <span className={cn("text-xs font-mono leading-none", iconConfig.color)}>
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
          // Subtle styling: background + border (no glow - de-emphasized)
          iconConfig.bgColor,
          iconConfig.borderColor
        )}
      >
      {/* Header (clickable to collapse) */}
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2",
          // UX: Cursor pointer
          "cursor-pointer",
          // UX: Subtle hover feedback
          "hover:bg-white/5 transition-colors duration-200 rounded-t-lg"
        )}
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
        <ChevronDown className={cn("h-3.5 w-3.5 shrink-0", iconConfig.color)} />

        {/* Message type icon */}
        <Icon className={cn("h-3.5 w-3.5 shrink-0", iconConfig.color)} />

        {/* Label text */}
        <span className={cn("text-xs font-mono leading-none", iconConfig.color)}>
          {label}
        </span>
      </div>

      {/* Content - subtle padding, no extra borders */}
      <div className="px-3 py-2 select-text cursor-text">
        {message.message_type === MessageType.ASSISTANT_TOOL_USE ? (
          // Tool use: show JSON formatted
          <pre className="text-xs font-mono text-slate-200 whitespace-pre-wrap break-words leading-relaxed overflow-x-auto">
            {JSON.stringify(message.contentParsed?.tool_input, null, 2)}
          </pre>
        ) : message.message_type === MessageType.ASSISTANT_TOOL_OUTPUT ? (
          // Tool output: handle null/empty
          <div className="text-xs font-mono text-slate-200 whitespace-pre-wrap break-words leading-relaxed">
            {(() => {
              const output = message.contentParsed?.tool_output
              if (output === undefined || output === null) {
                return <span className="text-slate-400 italic">Tool executed, no output</span>
              }
              if (typeof output === "string") {
                return output.trim() || <span className="text-slate-400 italic">Empty string</span>
              }
              return <pre className="overflow-x-auto">{JSON.stringify(output, null, 2)}</pre>
            })()}
          </div>
        ) : message.message_type === MessageType.ASSISTANT_PRE_COMPACT ? (
          // Pre-compact: info message
          <p className="text-xs text-slate-300 italic">
            Session context will be compacted to save tokens
          </p>
        ) : (
          // Default: message content (includes system messages)
          <p className="text-xs font-mono text-slate-200 whitespace-pre-wrap break-words leading-relaxed">
            {messageContent}
          </p>
        )}
      </div>
    </motion.div>
    </div>
  )
}
