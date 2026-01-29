/**
 * Animated Edge - Custom edge with particle animation
 */

import { getEventTypeColor } from "../../utils"
import { EdgeLabelRenderer } from "@xyflow/react"

interface AnimatedEdgeProps {
  id: string
  sourceX: number
  sourceY: number
  targetX: number
  targetY: number
  source: string
  target: string
  style?: any
  data?: {
    showTopology?: boolean
    eventType?: string
    connectionId?: number
    subscriptionCount?: number
    onContextMenu?: (e: React.MouseEvent, edgeId: string) => void
  }
}

export function AnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  source,
  target,
  style = {},
  data,
}: AnimatedEdgeProps) {
  const edgePath = `M ${sourceX},${sourceY} C ${sourceX + 50},${sourceY} ${targetX - 50},${targetY} ${targetX},${targetY}`
  const showTopology = data?.showTopology || false
  const eventType = data?.eventType || "node_message"
  const colors = getEventTypeColor(eventType)
  const subscriptionCount = data?.subscriptionCount || 0

  const midX = (sourceX + targetX) / 2
  const midY = (sourceY + targetY) / 2

  // Handle right-click
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    if (data?.onContextMenu) {
      data.onContextMenu(e, id)
    }
  }

  // If topology is not shown, make edge invisible but still interactive
  if (!showTopology) {
    return (
      <>
        <path
          id={id}
          data-edge-id={id}
          style={style}
          className="react-flow__edge-path stroke-transparent cursor-context-menu"
          d={edgePath}
          strokeWidth={20}
          fill="none"
          onContextMenu={handleContextMenu}
        />
      </>
    )
  }

  return (
    <>
      {/* Invisible wide path for easier clicking */}
      <path
        id={`${id}-hitbox`}
        data-edge-id={id}
        style={style}
        className="react-flow__edge-path stroke-transparent cursor-context-menu"
        d={edgePath}
        strokeWidth={20}
        fill="none"
        onContextMenu={handleContextMenu}
      />

      {/* Visible edge path */}
      <path
        id={id}
        style={{ ...style, stroke: colors.stroke }}
        className="react-flow__edge-path transition-all duration-300 hover:stroke-cyan-400 cursor-context-menu pointer-events-none"
        d={edgePath}
        strokeWidth={2}
        fill="none"
        opacity={0.6}
      />

      {/* Animated particle */}
      <circle r={3} fill={colors.fill} className="opacity-80 pointer-events-none">
        <animateMotion dur="3s" repeatCount="indefinite" path={edgePath} />
      </circle>

      {/* Event type label with subscription count */}
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${midX}px, ${midY}px)`,
            pointerEvents: "all",
          }}
          className="group"
        >
          <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-slate-900/90 px-2 py-1 backdrop-blur-xl transition-all hover:border-cyan-400/50 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]">
            <span className="font-mono text-xs font-medium" style={{ color: colors.stroke }}>
              {eventType}
            </span>
            {subscriptionCount > 0 && (
              <span className="rounded-full bg-cyan-500/20 px-1.5 py-0.5 text-xs font-semibold text-cyan-300">
                {subscriptionCount}
              </span>
            )}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export const edgeTypes = {
  animated: AnimatedEdge,
}
