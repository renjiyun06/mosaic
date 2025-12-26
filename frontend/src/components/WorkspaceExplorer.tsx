/**
 * Workspace file explorer component
 */
"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Folder,
  FolderOpen,
  FileText,
  FileCode,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Loader2,
  FolderX,
} from "lucide-react"
import { apiClient, WorkspaceEntry, WorkspaceFileResponse } from "@/lib/api"
import { useAuthStore } from "@/lib/store"
import { FilePreview } from "./FilePreview"

interface WorkspaceExplorerProps {
  nodeId: number
}

interface DirectoryState {
  [path: string]: {
    entries: WorkspaceEntry[]
    expanded: boolean
    loading: boolean
  }
}

export function WorkspaceExplorer({ nodeId }: WorkspaceExplorerProps) {
  const { token } = useAuthStore()
  const [directoryState, setDirectoryState] = useState<DirectoryState>({
    "": { entries: [], expanded: true, loading: false },
  })
  const [selectedFile, setSelectedFile] = useState<{
    path: string
    content: WorkspaceFileResponse
  } | null>(null)
  const [loadingFile, setLoadingFile] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Directory tree height state
  const [directoryHeight, setDirectoryHeight] = useState(300) // Default 300px

  // Refs
  const directoryPanelRef = useRef<HTMLDivElement>(null)

  // Drag state ref (pure ref, no state to avoid re-renders during drag)
  const dragStateRef = useRef({
    isDragging: false,
    startY: 0,
    startHeight: 0,
  })

  // Constants
  const DIRECTORY_MIN_HEIGHT = 100
  const DIRECTORY_DEFAULT_HEIGHT = 300
  const DIRECTORY_MAX_HEIGHT = 600

  // Load root directory on mount
  useEffect(() => {
    if (token) {
      loadDirectory("")
    }
  }, [nodeId, token])

  const loadDirectory = async (path: string) => {
    if (!token) return

    setError(null)
    setDirectoryState((prev) => ({
      ...prev,
      [path]: { ...prev[path], loading: true },
    }))

    try {
      const response = await apiClient.listWorkspaceDirectory(
        nodeId,
        token,
        path
      )

      setDirectoryState((prev) => ({
        ...prev,
        [path]: {
          entries: response.entries,
          expanded: true,
          loading: false,
        },
      }))
    } catch (err) {
      console.error("Failed to load directory:", err)
      setError(err instanceof Error ? err.message : "Failed to load directory")
      setDirectoryState((prev) => ({
        ...prev,
        [path]: { ...prev[path], loading: false },
      }))
    }
  }

  const loadFile = async (path: string) => {
    if (!token) return

    setLoadingFile(true)
    setError(null)

    try {
      const content = await apiClient.readWorkspaceFile(nodeId, token, path)
      setSelectedFile({ path, content })
    } catch (err) {
      console.error("Failed to load file:", err)
      setError(err instanceof Error ? err.message : "Failed to load file")
    } finally {
      setLoadingFile(false)
    }
  }

  const toggleDirectory = (path: string) => {
    const state = directoryState[path]
    if (!state) {
      // First time opening this directory
      loadDirectory(path)
    } else {
      // Toggle expanded state
      setDirectoryState((prev) => ({
        ...prev,
        [path]: { ...prev[path], expanded: !prev[path].expanded },
      }))
    }
  }

  const handleRefresh = () => {
    // Reload current directory
    loadDirectory("")
    setSelectedFile(null)
  }

  // Handle vertical drag start
  const handleDragStart = (e: React.MouseEvent) => {
    if (!directoryPanelRef.current) return

    e.preventDefault()

    dragStateRef.current = {
      isDragging: true,
      startY: e.clientY,
      startHeight: directoryHeight,
    }

    // Disable transition during drag for immediate response
    directoryPanelRef.current.style.transition = 'none'

    // Set cursor immediately
    document.body.style.cursor = 'row-resize'
    document.body.style.userSelect = 'none'

    // Define handlers as closures
    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!directoryPanelRef.current) return

      const deltaY = moveEvent.clientY - dragStateRef.current.startY
      const newHeight = Math.max(
        DIRECTORY_MIN_HEIGHT,
        Math.min(DIRECTORY_MAX_HEIGHT, dragStateRef.current.startHeight + deltaY)
      )

      // Update DOM directly without triggering React
      directoryPanelRef.current.style.height = `${newHeight}px`
    }

    const handleMouseUp = () => {
      if (!directoryPanelRef.current) return

      // Re-enable transition
      directoryPanelRef.current.style.transition = 'height 200ms ease-in-out'

      // Cleanup
      dragStateRef.current.isDragging = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''

      // Remove listeners
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)

      // Get final height and update state
      const finalHeight = parseInt(directoryPanelRef.current.style.height, 10)
      setDirectoryHeight(finalHeight)

      // Save to localStorage
      localStorage.setItem('workspace-directory-height', finalHeight.toString())
    }

    // Attach listeners immediately
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  // Load directory height from localStorage
  useEffect(() => {
    const savedHeight = localStorage.getItem('workspace-directory-height')

    if (savedHeight) {
      const height = parseInt(savedHeight, 10)
      if (height >= DIRECTORY_MIN_HEIGHT && height <= DIRECTORY_MAX_HEIGHT) {
        setDirectoryHeight(height)
      }
    }
  }, [])

  // Set initial transition and cleanup on unmount
  useEffect(() => {
    if (directoryPanelRef.current) {
      directoryPanelRef.current.style.transition = 'height 200ms ease-in-out'
    }

    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [])

  const renderFileIcon = (entry: WorkspaceEntry) => {
    if (entry.type === "directory") {
      const isExpanded = directoryState[entry.path]?.expanded
      return isExpanded ? (
        <FolderOpen className="h-4 w-4 text-blue-500" />
      ) : (
        <Folder className="h-4 w-4 text-blue-500" />
      )
    }

    // File icons based on extension
    const ext = entry.name.split(".").pop()?.toLowerCase()
    if (
      ext === "ts" ||
      ext === "tsx" ||
      ext === "js" ||
      ext === "jsx" ||
      ext === "py" ||
      ext === "json"
    ) {
      return <FileCode className="h-4 w-4 text-green-500" />
    }

    return <FileText className="h-4 w-4 text-gray-500" />
  }

  const renderEntry = (entry: WorkspaceEntry, level: number = 0) => {
    const isDirectory = entry.type === "directory"
    const isExpanded = directoryState[entry.path]?.expanded
    const isLoading = directoryState[entry.path]?.loading
    const isSelected = selectedFile?.path === entry.path

    return (
      <div key={entry.path}>
        <div
          className={`flex items-center gap-1 py-1 px-2 hover:bg-accent cursor-pointer ${
            isSelected ? "bg-accent" : ""
          }`}
          style={{ paddingLeft: `${level * 12 + 8}px` }}
          onClick={() => {
            if (isDirectory) {
              toggleDirectory(entry.path)
            } else {
              loadFile(entry.path)
            }
          }}
        >
          {isDirectory && (
            <div className="w-4 h-4 flex items-center justify-center">
              {isLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </div>
          )}
          {!isDirectory && <div className="w-4" />}
          {renderFileIcon(entry)}
          <span className="text-sm truncate flex-1">{entry.name}</span>
        </div>

        {/* Render subdirectory contents */}
        {isDirectory && isExpanded && directoryState[entry.path]?.entries && (
          <div>
            {directoryState[entry.path].entries.map((subEntry) =>
              renderEntry(subEntry, level + 1)
            )}
          </div>
        )}
      </div>
    )
  }

  const rootEntries = directoryState[""]?.entries || []
  const rootLoading = directoryState[""]?.loading

  return (
    <>
      {/* Header */}
      <div className="border-b bg-background px-6 flex items-center justify-between shrink-0 h-11">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-sm">工作目录</h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0"
          onClick={handleRefresh}
          disabled={rootLoading}
        >
          <RefreshCw
            className={`h-3 w-3 ${rootLoading ? "animate-spin" : ""}`}
          />
        </Button>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 bg-destructive/10 text-destructive text-xs">
          {error}
        </div>
      )}

      <div className="flex-1 flex flex-col min-h-0">
        {/* File tree */}
        <div
          ref={directoryPanelRef}
          className="overflow-hidden"
          style={{ height: `${directoryHeight}px` }}
        >
          <ScrollArea className="h-full">
            {rootLoading && rootEntries.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                加载中...
              </div>
            ) : rootEntries.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                <FolderX className="h-12 w-12 mx-auto mb-2 opacity-30" />
                <p>工作目录为空</p>
              </div>
            ) : (
              <div className="p-1">
                {rootEntries.map((entry) => renderEntry(entry))}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Resizable Divider */}
        <div
          className="py-1 cursor-row-resize"
          onMouseDown={handleDragStart}
          style={{ userSelect: 'none' }}
        >
          <div className="h-px bg-border hover:bg-muted-foreground/30 active:bg-muted-foreground/50 transition-colors" />
        </div>

        {/* File preview */}
        <div className="flex-1 overflow-hidden">
          {loadingFile ? (
            <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : selectedFile ? (
            <FilePreview
              fileName={selectedFile.path.split("/").pop() || ""}
              content={selectedFile.content.content}
              mimeType={selectedFile.content.mime_type}
              size={selectedFile.content.size}
              isTruncated={selectedFile.content.is_truncated}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
              <div className="text-center">
                <FileText className="h-12 w-12 mx-auto mb-2 opacity-30" />
                <p>选择文件以预览</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
