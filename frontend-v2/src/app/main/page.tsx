"use client"

/**
 * Mosaic Infinite Canvas - Main Page Entry
 * A futuristic control console with expandable nodes in canvas
 */

import { ReactFlowProvider } from "@xyflow/react"
import { InfiniteCanvas } from "./components/canvas"

export default function MainPage() {
  return (
    <ReactFlowProvider>
      <InfiniteCanvas />
    </ReactFlowProvider>
  )
}
