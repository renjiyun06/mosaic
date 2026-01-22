/**
 * Expanded Node Card - Large node card with chat interface
 */

import { useState } from "react"
import { motion } from "framer-motion"
import { Minimize2, Plus, MessageSquare, Send, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { type NodeProps } from "@xyflow/react"
import { mockSessions, mockMessages } from "../../constants"

export function ExpandedNodeCard({ data, selected }: NodeProps) {
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [inputMessage, setInputMessage] = useState("")
  const sessions = mockSessions[data.nodeId] || []
  const messages = selectedSession ? mockMessages[selectedSession] || [] : []

  const handleSendMessage = () => {
    if (inputMessage.trim()) {
      console.log("Sending:", inputMessage)
      setInputMessage("")
    }
  }

  return (
    <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", damping: 20, stiffness: 200 }}
        className={cn(
          "group relative flex h-[600px] w-[900px] flex-col overflow-hidden rounded-3xl border backdrop-blur-2xl transition-all",
          selected
            ? "border-cyan-400/80 shadow-[0_0_40px_rgba(34,211,238,0.5)]"
            : "border-cyan-400/50 shadow-[0_0_30px_rgba(34,211,238,0.3)]",
          "bg-gradient-to-br from-slate-900/95 to-slate-800/95"
        )}
      >

      {/* Animated border glow */}
      <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-400/20 via-blue-500/20 to-purple-500/20 opacity-50 blur-xl" />

      {/* Header */}
      <div className="relative z-10 flex items-center justify-between border-b border-white/10 bg-slate-900/50 p-4">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "h-2.5 w-2.5 rounded-full animate-pulse",
              data.status === "running"
                ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]"
                : "bg-slate-500"
            )}
          />
          <div>
            <h2 className="font-mono text-lg font-bold text-cyan-300">{data.id}</h2>
            <p className="text-xs text-slate-400">{data.type}</p>
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            data.onCollapse()
          }}
          className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
        >
          <Minimize2 className="h-5 w-5 text-slate-400 transition-colors group-hover:text-cyan-300" />
        </button>
      </div>

      {/* Main content area */}
      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* Left: Session list */}
        <div className="w-72 border-r border-white/10 bg-slate-900/30 p-3 backdrop-blur-sm overflow-y-auto">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-mono text-sm font-semibold text-white">Sessions</h3>
            <button className="group rounded-lg bg-cyan-500/20 p-1.5 transition-all hover:bg-cyan-500/30 hover:shadow-[0_0_12px_rgba(34,211,238,0.3)]">
              <Plus className="h-3.5 w-3.5 text-cyan-300" />
            </button>
          </div>

          <div className="space-y-2">
            {sessions.length === 0 ? (
              <div className="rounded-xl border border-white/5 bg-white/5 p-4 text-center">
                <MessageSquare className="mx-auto mb-2 h-6 w-6 text-slate-500" />
                <p className="text-xs text-slate-400">No sessions</p>
                <button className="mt-2 rounded-lg bg-cyan-500/20 px-3 py-1.5 text-xs font-medium text-cyan-300 transition-colors hover:bg-cyan-500/30">
                  Create
                </button>
              </div>
            ) : (
              sessions.map((session) => (
                <motion.button
                  key={session.id}
                  onClick={() => setSelectedSession(session.id)}
                  whileHover={{ x: 3 }}
                  className={cn(
                    "w-full rounded-xl border p-3 text-left transition-all",
                    selectedSession === session.id
                      ? "border-cyan-400/50 bg-cyan-500/20 shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                      : "border-white/10 bg-white/5 hover:border-cyan-400/30 hover:bg-white/10"
                  )}
                >
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className={cn(
                      "text-xs font-semibold line-clamp-1",
                      selectedSession === session.id ? "text-cyan-300" : "text-white"
                    )}>
                      {session.topic}
                    </span>
                    <div className={cn(
                      "h-1.5 w-1.5 rounded-full shrink-0",
                      session.status === "active" ? "bg-emerald-400 animate-pulse" : "bg-slate-500"
                    )} />
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span>{session.messageCount} msgs</span>
                    <span>{session.lastActivity}</span>
                  </div>
                </motion.button>
              ))
            )}
          </div>
        </div>

        {/* Right: Chat interface */}
        <div className="flex flex-1 flex-col">
          {selectedSession ? (
            <>
              {/* Messages area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "flex",
                      msg.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    <div className={cn(
                      "max-w-[75%] rounded-xl border p-3 backdrop-blur-xl",
                      msg.role === "user"
                        ? "border-cyan-400/30 bg-cyan-500/20"
                        : "border-white/10 bg-slate-800/50"
                    )}>
                      <p className="text-xs text-white">{msg.content}</p>
                      <span className="mt-1.5 block text-[10px] text-slate-400">{msg.timestamp}</span>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Input area */}
              <div className="border-t border-white/10 bg-slate-900/50 p-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                    placeholder="Type your message..."
                    className="flex-1 rounded-xl border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none focus:ring-2 focus:ring-cyan-400/20 backdrop-blur-xl"
                  />
                  <button
                    onClick={handleSendMessage}
                    className="group rounded-xl border border-cyan-400/30 bg-cyan-500/20 px-4 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/30 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
                  >
                    <Send className="h-4 w-4 text-cyan-300" />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <Sparkles className="mx-auto mb-3 h-10 w-10 text-cyan-400/50" />
                <p className="text-sm text-slate-400">Select a session</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
