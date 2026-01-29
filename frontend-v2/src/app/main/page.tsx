"use client"

/**
 * Mosaic Infinite Canvas - Main Page Entry
 * A futuristic control console with expandable nodes in canvas
 *
 * Provider Hierarchy:
 * 1. ThemeProvider (outermost) - Manages dual theme system
 * 2. ReactFlowProvider - Manages canvas state
 * 3. InfiniteCanvas - Main canvas component
 */

import { ReactFlowProvider } from "@xyflow/react"
import { InfiniteCanvas } from "./components/canvas"
import { ThemeProvider } from "./contexts/ThemeContext"

export default function MainPage() {
  return (
    <ThemeProvider>
      <ReactFlowProvider>
        <InfiniteCanvas />
      </ReactFlowProvider>
    </ThemeProvider>
  )
}
