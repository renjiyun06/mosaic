"use client"

/**
 * Geometry Canvas Page - Interactive geometry teaching canvas
 *
 * Features:
 * - Infinite canvas powered by tldraw
 * - Integrated GeoGebra instances for precise geometry construction
 * - Chat panel with flexible node selection for AI assistance
 * - Supports multiple GeoGebra instances on the same canvas
 * - Independent from specific mosaic instances
 */

import { useEffect, useState } from "react"
import dynamic from "next/dynamic"
import { ChatPanel } from "./components/ChatPanel"

// Dynamically import TldrawCanvas to avoid SSR issues
const TldrawCanvas = dynamic(
  () => import("./components/TldrawCanvas"),
  { ssr: false }
)

export default function GeometryCanvasPage() {
  const [mounted, setMounted] = useState(false)
  const [editor, setEditor] = useState<any>(null)
  const [isChatVisible, setIsChatVisible] = useState(true)

  useEffect(() => {
    setMounted(true)
  }, [])

  const handleEditorReady = (editorInstance: any) => {
    setEditor(editorInstance)
    console.log('Editor ready:', editorInstance)
  }

  if (!mounted) {
    return null
  }

  return (
    <div className="absolute inset-0 flex bg-background">
      {/* Canvas + Chat Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Canvas Area */}
        <div className="flex-1 relative">
          <TldrawCanvas onEditorReady={handleEditorReady} />
        </div>

        {/* Chat Panel (collapsible) */}
        <ChatPanel
          editor={editor}
          isVisible={isChatVisible}
          onToggle={() => setIsChatVisible(!isChatVisible)}
        />
      </div>
    </div>
  )
}
