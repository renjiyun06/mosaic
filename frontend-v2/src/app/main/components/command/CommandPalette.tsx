/**
 * Command Palette - Quick command launcher (Cmd+K)
 * Dual-theme support with glassmorphism and accessibility
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Command } from "cmdk"
import { Search, X, Plus, Network, Terminal } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTheme } from "../../hooks/useTheme"

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'
  const [search, setSearch] = useState("")

  useEffect(() => {
    if (open) {
      setSearch("")
    }
  }, [open])

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className={cn(
              "fixed inset-0 z-[100]",
              !isAppleGlass && "bg-black/60 backdrop-blur-sm"
            )}
            style={
              isAppleGlass
                ? {
                    // Apple Glass: Same as Dialog backdrop
                    background: "rgba(15, 23, 42, 0.4)",
                    backdropFilter: "blur(12px)",
                  }
                : undefined
            }
          />

          {/* Command Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            className="fixed left-1/2 top-32 z-[101] w-full max-w-2xl -translate-x-1/2"
          >
            <Command
              className={cn(
                "overflow-hidden rounded-2xl border",
                !isAppleGlass &&
                  "border-cyan-400/30 bg-slate-900/95 shadow-[0_0_50px_rgba(34,211,238,0.3)] backdrop-blur-xl"
              )}
              style={
                isAppleGlass
                  ? {
                      // Apple Glass: 3% glass effect
                      background: "var(--glass-background)",
                      backdropFilter: "var(--backdrop-blur)",
                      borderColor: "var(--glass-border)",
                      boxShadow: "var(--shadow-glass), var(--shadow-glassInset)",
                    }
                  : undefined
              }
            >
              <div
                className={cn(
                  "flex items-center border-b px-4",
                  !isAppleGlass && "border-white/10"
                )}
                style={
                  isAppleGlass
                    ? {
                        borderColor: "var(--glass-border)",
                      }
                    : undefined
                }
              >
                <Search
                  className={cn("h-5 w-5", !isAppleGlass && "text-slate-400")}
                  style={isAppleGlass ? { color: "var(--color-text-muted)" } : undefined}
                />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  placeholder="Type a command or search..."
                  className={cn(
                    "flex-1 border-none bg-transparent px-4 py-5 focus:outline-none",
                    !isAppleGlass && "text-white placeholder:text-slate-500"
                  )}
                  style={
                    isAppleGlass
                      ? {
                          color: "var(--color-text-primary)",
                        }
                      : undefined
                  }
                />
                <button
                  onClick={onClose}
                  className={cn(
                    "rounded-lg p-1 transition-colors",
                    !isAppleGlass && "text-slate-400 hover:bg-white/10 hover:text-white"
                  )}
                  style={
                    isAppleGlass
                      ? {
                          color: "var(--color-text-muted)",
                        }
                      : undefined
                  }
                  onMouseEnter={(e) => {
                    if (isAppleGlass) {
                      e.currentTarget.style.background = "rgba(239, 68, 68, 0.1)"
                      e.currentTarget.style.color = "#ef4444"
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (isAppleGlass) {
                      e.currentTarget.style.background = "transparent"
                      e.currentTarget.style.color = "var(--color-text-muted)"
                    }
                  }}
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <Command.List className="max-h-96 overflow-y-auto p-2 cyberpunk-scrollbar">
                <Command.Empty
                  className={cn("py-10 text-center text-sm", !isAppleGlass && "text-slate-400")}
                  style={isAppleGlass ? { color: "var(--color-text-muted)" } : undefined}
                >
                  No results found.
                </Command.Empty>

                <Command.Group heading="Actions" className="mb-2">
                  <div
                    className={cn("mb-2 px-2 text-xs font-semibold", !isAppleGlass && "text-slate-500")}
                    style={isAppleGlass ? { color: "var(--color-text-muted)" } : undefined}
                  >
                    ACTIONS
                  </div>
                  {[
                    { icon: Plus, label: "Create Node", shortcut: "⌘N" },
                    { icon: Network, label: "Create Connection", shortcut: "⌘L" },
                    { icon: Terminal, label: "Open Terminal", shortcut: "⌘T" },
                  ].map((item, i) => (
                    <Command.Item
                      key={i}
                      className={cn(
                        "flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
                        !isAppleGlass &&
                          "text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 data-[selected=true]:bg-cyan-500/20 data-[selected=true]:text-cyan-300"
                      )}
                      style={
                        isAppleGlass
                          ? {
                              color: "var(--color-text-primary)",
                            }
                          : undefined
                      }
                      onMouseEnter={(e) => {
                        if (isAppleGlass) {
                          e.currentTarget.style.background = "rgba(59, 130, 246, 0.1)"
                          e.currentTarget.style.color = "var(--color-accent)"
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (isAppleGlass) {
                          e.currentTarget.style.background = "transparent"
                          e.currentTarget.style.color = "var(--color-text-primary)"
                        }
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <item.icon className="h-4 w-4" />
                        <span>{item.label}</span>
                      </div>
                      <kbd
                        className={cn(
                          "rounded px-2 py-1 font-mono text-xs",
                          !isAppleGlass && "bg-slate-800 text-slate-400"
                        )}
                        style={
                          isAppleGlass
                            ? {
                                background: "rgba(255, 255, 255, 0.05)",
                                borderColor: "var(--glass-border)",
                                border: "0.5px solid",
                                color: "var(--color-text-muted)",
                              }
                            : undefined
                        }
                      >
                        {item.shortcut}
                      </kbd>
                    </Command.Item>
                  ))}
                </Command.Group>

                <Command.Group heading="Nodes" className="mb-2">
                  <div
                    className={cn("mb-2 px-2 text-xs font-semibold", !isAppleGlass && "text-slate-500")}
                    style={isAppleGlass ? { color: "var(--color-text-muted)" } : undefined}
                  >
                    NODES
                  </div>
                  {["mosaic-develop", "advanced-programmer", "deep-search", "deep-wiki"].map((node, i) => (
                    <Command.Item
                      key={i}
                      className={cn(
                        "flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
                        !isAppleGlass &&
                          "text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 data-[selected=true]:bg-cyan-500/20 data-[selected=true]:text-cyan-300"
                      )}
                      style={
                        isAppleGlass
                          ? {
                              color: "var(--color-text-primary)",
                            }
                          : undefined
                      }
                      onMouseEnter={(e) => {
                        if (isAppleGlass) {
                          e.currentTarget.style.background = "rgba(59, 130, 246, 0.1)"
                          e.currentTarget.style.color = "var(--color-accent)"
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (isAppleGlass) {
                          e.currentTarget.style.background = "transparent"
                          e.currentTarget.style.color = "var(--color-text-primary)"
                        }
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={cn("h-2 w-2 rounded-full", !isAppleGlass && "bg-emerald-400")}
                          style={isAppleGlass ? { background: "var(--color-success)" } : undefined}
                        />
                        <span className="font-mono">{node}</span>
                      </div>
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
