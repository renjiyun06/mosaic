/**
 * Canvas UI state hook - manages dialogs, sidebars, and UI toggles
 */

import { useState, useEffect } from "react"

export function useCanvasState() {
  const [commandOpen, setCommandOpen] = useState(false)
  const [createNodeOpen, setCreateNodeOpen] = useState(false)
  const [connectionsSidebarOpen, setConnectionsSidebarOpen] = useState(false)
  const [showTopology, setShowTopology] = useState(false)

  return {
    commandOpen,
    setCommandOpen,
    createNodeOpen,
    setCreateNodeOpen,
    connectionsSidebarOpen,
    setConnectionsSidebarOpen,
    showTopology,
    setShowTopology,
    toggleTopology: () => setShowTopology(!showTopology),
  }
}
