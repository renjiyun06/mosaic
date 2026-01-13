import { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import {
  Loader2,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Folder,
  FolderOpen,
  File,
  FileText,
  FileCode,
  Terminal as TerminalIcon,
  Trash2,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { useWebSocket } from "@/contexts/websocket-context"
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { SerializeAddon } from '@xterm/addon-serialize'
import '@xterm/xterm/css/xterm.css'
import type { WorkspaceFileItem } from "@/lib/types"

interface FileNode extends WorkspaceFileItem {
  expanded?: boolean
}

interface WorkspaceViewProps {
  sessionId: string
  nodeId: string
  mosaicId: number
  isVisible: boolean
}

export function WorkspaceView({
  sessionId,
  nodeId,
  mosaicId,
  isVisible,
}: WorkspaceViewProps) {
  const { sendRaw, subscribe } = useWebSocket()

  // File tree state
  const [fileTree, setFileTree] = useState<FileNode[]>([])
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string; language: string | null } | null>(null)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [fileContentLoading, setFileContentLoading] = useState(false)

  // Sidebar state (resizable & collapsible)
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    if (typeof window === 'undefined') return 280
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-sidebar-width`)
      return saved ? parseInt(saved, 10) : 280
    } catch (error) {
      return 280
    }
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-sidebar-collapsed`)
      return saved === 'true'
    } catch (error) {
      return false
    }
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeStartX = useRef<number>(0)
  const resizeStartWidth = useRef<number>(0)

  // Terminal state (resizable & collapsible)
  const [terminalHeight, setTerminalHeight] = useState<number>(() => {
    if (typeof window === 'undefined') return 300
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-terminal-height`)
      return saved ? parseInt(saved, 10) : 300
    } catch (error) {
      return 300
    }
  })
  const [terminalCollapsed, setTerminalCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      const saved = localStorage.getItem(`mosaic-${mosaicId}-terminal-collapsed`)
      return saved === 'true'
    } catch (error) {
      return false
    }
  })
  const [isTerminalResizing, setIsTerminalResizing] = useState(false)
  const terminalResizeStartY = useRef<number>(0)
  const terminalResizeStartHeight = useRef<number>(0)

  // Terminal refs
  const terminalRef = useRef<HTMLDivElement>(null)
  const terminalInstanceRef = useRef<{
    terminal: Terminal | null
    fitAddon: FitAddon | null
    serializeAddon: SerializeAddon | null
    serializedContent: string
  }>({
    terminal: null,
    fitAddon: null,
    serializeAddon: null,
    serializedContent: ''
  })

  // Load workspace files on mount or when nodeId changes
  useEffect(() => {
    if (nodeId) {
      loadWorkspace()
    }
  }, [nodeId])

  // WebSocket subscription for terminal messages
  useEffect(() => {
    const unsubscribe = subscribe(sessionId, (message) => {
      // Check if it's an error message
      if ("type" in message && message.type === "error") {
        return
      }

      const wsMessage = message as import("@/contexts/websocket-context").WSMessage

      // Handle terminal messages
      if (wsMessage.message_type === 'terminal_output') {
        console.log('[WorkspaceView] Received terminal_output:', {
          session_id: wsMessage.session_id,
          data_length: wsMessage.payload?.data?.length
        })

        if (wsMessage.payload?.data && terminalInstanceRef.current.terminal) {
          terminalInstanceRef.current.terminal.write(wsMessage.payload.data)
        }
      }

      if (wsMessage.message_type === 'terminal_status') {
        console.log('[WorkspaceView] Received terminal_status:', {
          session_id: wsMessage.session_id,
          status: wsMessage.payload?.status
        })

        if (terminalInstanceRef.current.terminal) {
          if (wsMessage.payload?.status === 'started') {
            terminalInstanceRef.current.terminal.write('\r\nTerminal connected.\r\n')
          } else if (wsMessage.payload?.status === 'stopped') {
            terminalInstanceRef.current.terminal.write('\r\nTerminal disconnected.\r\n')
          } else if (wsMessage.payload?.status === 'error' && wsMessage.payload?.message) {
            terminalInstanceRef.current.terminal.write(`\r\n\x1b[31mError: ${wsMessage.payload.message}\x1b[0m\r\n`)
          }
        }
      }
    })

    return () => {
      unsubscribe()
    }
  }, [sessionId, subscribe])

  // Terminal initialization
  useEffect(() => {
    if (isVisible && !terminalCollapsed && terminalRef.current) {
      console.log('[WorkspaceView] Creating terminal instance for session:', sessionId)

      const term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'monospace, "Courier New", Courier',
        theme: {
          background: '#1a1a1a',
          foreground: '#00ff00',
          cursor: '#00ff00',
          cursorAccent: '#1a1a1a',
        },
        convertEol: true,
        scrollback: 1000,
      })

      const fit = new FitAddon()
      const serialize = new SerializeAddon()
      term.loadAddon(fit)
      term.loadAddon(serialize)

      // Clear the container and open terminal
      terminalRef.current.innerHTML = ''
      term.open(terminalRef.current)
      fit.fit()

      // Restore serialized content if exists
      if (terminalInstanceRef.current.serializedContent) {
        console.log('[WorkspaceView] Restoring serialized content')
        term.write(terminalInstanceRef.current.serializedContent)
      } else {
        // Display welcome message for new terminals
        term.writeln('Welcome to Mosaic Terminal')
        term.writeln('Waiting for connection...')
        term.writeln('')
      }

      // Handle user input
      term.onData((data) => {
        console.log('[WorkspaceView] Sending terminal_input, data length:', data.length)
        sendRaw({
          session_id: sessionId,
          type: 'terminal_input',
          data: data
        })
      })

      // Update terminal instance
      terminalInstanceRef.current.terminal = term
      terminalInstanceRef.current.fitAddon = fit
      terminalInstanceRef.current.serializeAddon = serialize

      // Send terminal_start message if this is the first terminal
      if (!terminalInstanceRef.current.serializedContent) {
        console.log('[WorkspaceView] Sending terminal_start for session:', sessionId)
        sendRaw({
          session_id: sessionId,
          type: 'terminal_start'
        })

        // Send initial newline to trigger bash prompt display
        setTimeout(() => {
          sendRaw({
            session_id: sessionId,
            type: 'terminal_input',
            data: '\r'
          })
        }, 200)
      }

      term.focus()

      // Cleanup function
      return () => {
        console.log('[WorkspaceView] Saving and disposing terminal for session:', sessionId)

        // Save serialized content
        if (terminalInstanceRef.current.serializeAddon) {
          terminalInstanceRef.current.serializedContent = terminalInstanceRef.current.serializeAddon.serialize()
        }

        // Dispose terminal
        if (terminalInstanceRef.current.terminal) {
          terminalInstanceRef.current.terminal.dispose()
          terminalInstanceRef.current.terminal = null
          terminalInstanceRef.current.fitAddon = null
          terminalInstanceRef.current.serializeAddon = null
        }
      }
    }
  }, [isVisible, terminalCollapsed, sessionId, sendRaw])

  // Terminal resize
  useEffect(() => {
    if (isVisible && !terminalCollapsed && terminalInstanceRef.current.fitAddon) {
      const timeoutId = setTimeout(() => {
        if (terminalInstanceRef.current.fitAddon) {
          terminalInstanceRef.current.fitAddon.fit()
        }
      }, 100)
      return () => clearTimeout(timeoutId)
    }
  }, [isVisible, terminalCollapsed, terminalHeight, sidebarWidth])

  // Load workspace files
  const loadWorkspace = async () => {
    if (!nodeId) return

    try {
      setWorkspaceLoading(true)
      const data = await apiClient.listWorkspaceFiles(mosaicId, nodeId, {
        path: '/',
        recursive: false,
        max_depth: 1
      })

      // Convert WorkspaceFileItem[] to FileNode[]
      const convertToFileNodes = (items: WorkspaceFileItem[]): FileNode[] => {
        return items.map(item => ({
          ...item,
          expanded: false,
          children: item.type === 'directory'
            ? (item.children ? convertToFileNodes(item.children) : undefined)
            : undefined
        }))
      }

      setFileTree(convertToFileNodes(data.items))
    } catch (error) {
      console.error("Failed to load workspace:", error)
      setFileTree([])
    } finally {
      setWorkspaceLoading(false)
    }
  }

  // Load directory children (lazy loading)
  const loadDirectoryChildren = async (path: string) => {
    try {
      const data = await apiClient.listWorkspaceFiles(mosaicId, nodeId, {
        path: path,
        recursive: false,
        max_depth: 1
      })

      const convertToFileNodes = (items: WorkspaceFileItem[]): FileNode[] => {
        return items.map(item => ({
          ...item,
          expanded: false,
          children: item.type === 'directory' ? undefined : undefined
        }))
      }

      return convertToFileNodes(data.items)
    } catch (error) {
      console.error(`Failed to load directory: ${path}`, error)
      return []
    }
  }

  // Toggle directory expand/collapse
  const toggleDirectory = async (path: string) => {
    const findNode = (nodes: FileNode[]): FileNode | null => {
      for (const node of nodes) {
        if (node.path === path) return node
        if (node.children) {
          const found = findNode(node.children)
          if (found) return found
        }
      }
      return null
    }

    const targetNode = findNode(fileTree)

    // If expanding and children not loaded, load them first
    if (targetNode && !targetNode.expanded && targetNode.children === undefined) {
      const children = await loadDirectoryChildren(path)

      const updateTree = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(node => {
          if (node.path === path) {
            return { ...node, expanded: true, children }
          }
          if (node.children) {
            return { ...node, children: updateTree(node.children) }
          }
          return node
        })
      }
      setFileTree(updateTree(fileTree))
    } else {
      // Just toggle expanded state
      const toggleInTree = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(node => {
          if (node.path === path && node.type === 'directory') {
            return { ...node, expanded: !node.expanded }
          }
          if (node.children) {
            return { ...node, children: toggleInTree(node.children) }
          }
          return node
        })
      }
      setFileTree(toggleInTree(fileTree))
    }
  }

  // Load file content
  const handleFileClick = async (path: string) => {
    if (!nodeId) return

    try {
      setFileContentLoading(true)
      const data = await apiClient.getWorkspaceFileContent(mosaicId, nodeId, {
        path,
        encoding: 'utf-8',
        max_size: 1048576 // 1MB
      })

      setSelectedFile({
        path: data.path,
        content: data.content,
        language: data.language
      })
    } catch (error) {
      console.error("Failed to load file content:", error)
      setSelectedFile({
        path,
        content: `// Failed to load file: ${error}`,
        language: null
      })
    } finally {
      setFileContentLoading(false)
    }
  }

  // Render file tree recursively
  const renderFileTree = (nodes: FileNode[], level: number = 0) => {
    return nodes.map((node) => (
      <div key={node.path}>
        <div
          className={`flex items-center gap-2 px-2 py-1 hover:bg-muted/50 cursor-pointer ${
            selectedFile?.path === node.path ? 'bg-muted' : ''
          }`}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onClick={async () => {
            if (node.type === 'directory') {
              await toggleDirectory(node.path)
            } else {
              handleFileClick(node.path)
            }
          }}
        >
          {node.type === 'directory' ? (
            <>
              {node.expanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              {node.expanded ? (
                <FolderOpen className="h-4 w-4 shrink-0 text-yellow-500" />
              ) : (
                <Folder className="h-4 w-4 shrink-0 text-yellow-500" />
              )}
            </>
          ) : (
            <>
              <span className="w-4 shrink-0" />
              {node.name.endsWith('.tsx') || node.name.endsWith('.ts') || node.name.endsWith('.jsx') || node.name.endsWith('.js') ? (
                <FileCode className="h-4 w-4 shrink-0 text-blue-500" />
              ) : node.name.endsWith('.json') ? (
                <FileText className="h-4 w-4 shrink-0 text-green-500" />
              ) : node.name.endsWith('.md') ? (
                <FileText className="h-4 w-4 shrink-0 text-purple-500" />
              ) : (
                <File className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
            </>
          )}
          <span className="text-sm whitespace-nowrap">{node.name}</span>
        </div>
        {node.type === 'directory' && node.expanded && node.children && (
          <div>{renderFileTree(node.children, level + 1)}</div>
        )}
      </div>
    ))
  }

  // Sidebar resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    resizeStartX.current = e.clientX
    resizeStartWidth.current = sidebarWidth
  }, [sidebarWidth])

  const handleResizeMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return

    const deltaX = e.clientX - resizeStartX.current
    const newWidth = resizeStartWidth.current + deltaX
    const constrainedWidth = Math.min(Math.max(newWidth, 200), 600)
    setSidebarWidth(constrainedWidth)
  }, [isResizing])

  const handleResizeEnd = useCallback(() => {
    if (!isResizing) return
    setIsResizing(false)
  }, [isResizing])

  // Terminal resize handlers
  const handleTerminalResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsTerminalResizing(true)
    terminalResizeStartY.current = e.clientY
    terminalResizeStartHeight.current = terminalHeight
  }, [terminalHeight])

  const handleTerminalResizeMove = useCallback((e: MouseEvent) => {
    if (!isTerminalResizing) return

    const deltaY = terminalResizeStartY.current - e.clientY
    const newHeight = terminalResizeStartHeight.current + deltaY
    const constrainedHeight = Math.min(Math.max(newHeight, 150), 800)
    setTerminalHeight(constrainedHeight)
  }, [isTerminalResizing])

  const handleTerminalResizeEnd = useCallback(() => {
    if (!isTerminalResizing) return
    setIsTerminalResizing(false)
  }, [isTerminalResizing])

  // Attach global mouse event listeners for resizing
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove)
      document.addEventListener('mouseup', handleResizeEnd)
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'

      return () => {
        document.removeEventListener('mousemove', handleResizeMove)
        document.removeEventListener('mouseup', handleResizeEnd)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
    }
  }, [isResizing, handleResizeMove, handleResizeEnd])

  useEffect(() => {
    if (isTerminalResizing) {
      document.addEventListener('mousemove', handleTerminalResizeMove)
      document.addEventListener('mouseup', handleTerminalResizeEnd)
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'row-resize'

      return () => {
        document.removeEventListener('mousemove', handleTerminalResizeMove)
        document.removeEventListener('mouseup', handleTerminalResizeEnd)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
    }
  }, [isTerminalResizing, handleTerminalResizeMove, handleTerminalResizeEnd])

  // Save states to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-sidebar-width`, sidebarWidth.toString())
    } catch (error) {
      console.error("Failed to save sidebar width:", error)
    }
  }, [sidebarWidth, mosaicId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-sidebar-collapsed`, sidebarCollapsed.toString())
    } catch (error) {
      console.error("Failed to save sidebar collapsed state:", error)
    }
  }, [sidebarCollapsed, mosaicId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-terminal-height`, terminalHeight.toString())
    } catch (error) {
      console.error("Failed to save terminal height:", error)
    }
  }, [terminalHeight, mosaicId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(`mosaic-${mosaicId}-terminal-collapsed`, terminalCollapsed.toString())
    } catch (error) {
      console.error("Failed to save terminal collapsed state:", error)
    }
  }, [terminalCollapsed, mosaicId])

  // Toggle functions
  const toggleSidebarCollapse = useCallback(() => {
    setSidebarCollapsed(prev => !prev)
  }, [])

  const toggleTerminalCollapse = useCallback(() => {
    setTerminalCollapsed(prev => !prev)
  }, [])

  // Restart terminal
  const handleRestartTerminal = useCallback(() => {
    console.log('[WorkspaceView] Restarting terminal for session:', sessionId)

    // Stop backend terminal
    sendRaw({
      session_id: sessionId,
      type: 'terminal_stop'
    })

    // Clear terminal
    terminalInstanceRef.current.serializedContent = ''
    if (terminalInstanceRef.current.terminal) {
      terminalInstanceRef.current.terminal.clear()
      terminalInstanceRef.current.terminal.writeln('Terminal restarting...')
    }

    // Restart after delay
    setTimeout(() => {
      sendRaw({
        session_id: sessionId,
        type: 'terminal_start'
      })

      setTimeout(() => {
        sendRaw({
          session_id: sessionId,
          type: 'terminal_input',
          data: '\r'
        })
      }, 200)
    }, 100)
  }, [sessionId, sendRaw])

  if (!isVisible) {
    return null
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: File Tree - Resizable & Collapsible */}
      <div
        className="bg-background overflow-hidden flex flex-col"
        style={{
          width: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
          minWidth: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
          maxWidth: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
          transition: sidebarCollapsed ? 'width 0.2s ease-in-out' : 'none',
        }}
      >
        {/* Header */}
        <div className="px-3 py-1.5 border-b bg-background flex items-center justify-between shrink-0">
          {!sidebarCollapsed ? (
            <>
              <div className="flex items-center gap-2">
                <Folder className="h-4 w-4" />
                <span className="text-sm font-medium">文件树</span>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  onClick={loadWorkspace}
                  disabled={workspaceLoading}
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${workspaceLoading ? 'animate-spin' : ''}`} />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  onClick={toggleSidebarCollapse}
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 mx-auto"
              onClick={toggleSidebarCollapse}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        {/* File Tree Content */}
        {!sidebarCollapsed && (
          <div className="py-2 overflow-auto flex-1">
            {workspaceLoading ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                <Loader2 className="h-5 w-5 sm:h-6 sm:w-6 animate-spin mx-auto mb-2" />
                <span className="text-xs sm:text-sm">加载中...</span>
              </div>
            ) : fileTree.length === 0 ? (
              <div className="p-4 text-center text-xs sm:text-sm text-muted-foreground">
                工作区为空
              </div>
            ) : (
              renderFileTree(fileTree)
            )}
          </div>
        )}
      </div>

      {/* Resize Handle - Draggable divider */}
      {!sidebarCollapsed && (
        <div
          className="relative shrink-0 cursor-col-resize group"
          onMouseDown={handleResizeStart}
          style={{ width: '16px' }}
        >
          <div
            className="absolute left-1/2 top-0 bottom-0 -translate-x-1/2 w-px bg-border group-hover:w-0.5 group-hover:bg-muted-foreground/50"
            style={{
              width: isResizing ? '2px' : undefined,
              backgroundColor: isResizing ? 'hsl(var(--muted-foreground) / 0.5)' : undefined,
            }}
          />
        </div>
      )}

      {/* Right: File Content Viewer & Terminal (Split Vertically) */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top: File Content Viewer */}
        <div
          className="flex flex-col bg-muted/20 overflow-hidden"
          style={{
            height: terminalCollapsed ? '100%' : `calc(100% - ${terminalHeight}px - 16px)`,
          }}
        >
          {fileContentLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Loader2 className="h-8 w-8 sm:h-10 sm:w-10 md:h-12 md:w-12 animate-spin mx-auto mb-2" />
                <p className="text-xs sm:text-sm">加载文件内容...</p>
              </div>
            </div>
          ) : selectedFile ? (
            <>
              {/* File header */}
              <div className="border-b bg-background px-2 sm:px-3 md:px-4 py-2 shrink-0">
                <div className="flex items-center gap-2">
                  <FileCode className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-blue-500 shrink-0" />
                  <span className="text-xs sm:text-sm font-mono truncate">{selectedFile.path}</span>
                </div>
              </div>
              {/* File content */}
              <div className="flex-1 overflow-auto">
                <pre className="p-2 sm:p-3 md:p-4 text-xs sm:text-sm font-mono">
                  <code>{selectedFile.content}</code>
                </pre>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground px-4">
                <FileText className="h-12 w-12 sm:h-14 sm:w-14 md:h-16 md:w-16 mx-auto mb-3 sm:mb-4 opacity-30" />
                <p className="text-sm sm:text-base">选择一个文件查看内容</p>
              </div>
            </div>
          )}
        </div>

        {/* Terminal Resize Handle - Draggable divider */}
        {!terminalCollapsed && (
          <div
            className="relative shrink-0 cursor-row-resize group"
            onMouseDown={handleTerminalResizeStart}
            style={{ height: '16px' }}
          >
            <div
              className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-px bg-border group-hover:h-0.5 group-hover:bg-muted-foreground/50"
              style={{
                height: isTerminalResizing ? '2px' : undefined,
                backgroundColor: isTerminalResizing ? 'hsl(var(--muted-foreground) / 0.5)' : undefined,
              }}
            />
          </div>
        )}

        {/* Bottom: Terminal Panel */}
        <div
          className="bg-background overflow-hidden flex flex-col border-t"
          style={{
            height: terminalCollapsed ? '40px' : `${terminalHeight}px`,
            minHeight: terminalCollapsed ? '40px' : `${terminalHeight}px`,
            maxHeight: terminalCollapsed ? '40px' : `${terminalHeight}px`,
            transition: terminalCollapsed ? 'height 0.2s ease-in-out' : 'none',
          }}
        >
          {/* Terminal Header */}
          <div className="px-3 py-2 border-b bg-background flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <TerminalIcon className="h-4 w-4" />
              <span className="text-sm font-medium">终端</span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={handleRestartTerminal}
                title="Clear and restart terminal"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={toggleTerminalCollapse}
              >
                {terminalCollapsed ? (
                  <ChevronUp className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" />
                )}
              </Button>
            </div>
          </div>

          {/* Terminal Content */}
          <div
            ref={terminalRef}
            className="flex-1 overflow-hidden"
            style={{
              height: '100%',
              width: '100%',
              display: terminalCollapsed ? 'none' : 'block'
            }}
          />
        </div>
      </div>
    </div>
  )
}
