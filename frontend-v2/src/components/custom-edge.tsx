"use client"

import { EdgeProps, useStore } from "@xyflow/react"
import { useMemo } from "react"

export default function CustomEdge({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  style = {},
  markerEnd,
  label,
  labelStyle,
  labelBgStyle,
  data,
}: EdgeProps) {
  // Get node information to calculate center positions
  const sourceNode = useStore((state) => state.nodeLookup.get(source))
  const targetNode = useStore((state) => state.nodeLookup.get(target))

  // Calculate offset for multiple edges
  const offset = (data?.offset as number | undefined) || 0

  // Calculate path and control point using node centers
  const { customPath, labelX, labelY } = useMemo(() => {
    // Calculate source and target center positions
    const sourceCenterX = sourceNode
      ? sourceNode.position.x + (sourceNode.measured?.width || 100) / 2
      : sourceX
    const sourceCenterY = sourceNode
      ? sourceNode.position.y + (sourceNode.measured?.height || 35) / 2
      : sourceY

    const targetCenterX = targetNode
      ? targetNode.position.x + (targetNode.measured?.width || 100) / 2
      : targetX
    const targetCenterY = targetNode
      ? targetNode.position.y + (targetNode.measured?.height || 35) / 2
      : targetY

    // Handle self-loop (node connecting to itself)
    if (source === target) {
      const nodeWidth = sourceNode?.measured?.width || 100
      const nodeHeight = sourceNode?.measured?.height || 35

      // Loop size based on offset (allows multiple self-loops with different sizes)
      const loopSize = 60 + Math.abs(offset) * 20

      // Start point: right edge center
      const startX = sourceCenterX + nodeWidth / 2
      const startY = sourceCenterY

      // Control point 1: extend far to the right and slightly up
      const cp1X = sourceCenterX + nodeWidth / 2 + loopSize * 1.2
      const cp1Y = sourceCenterY - loopSize * 0.3

      // Control point 2: extend far upward and slightly right
      const cp2X = sourceCenterX + loopSize * 0.3
      const cp2Y = sourceCenterY - nodeHeight / 2 - loopSize * 1.2

      // End point: top edge center
      const endX = sourceCenterX
      const endY = sourceCenterY - nodeHeight / 2

      // Create cubic bezier path for self-loop
      const customPath = `M ${startX},${startY} C ${cp1X},${cp1Y} ${cp2X},${cp2Y} ${endX},${endY}`

      // Label position: visual center of the loop
      const labelX = sourceCenterX + loopSize * 0.6
      const labelY = sourceCenterY - loopSize * 0.6

      return { customPath, labelX, labelY }
    }

    // Normal edge (different source and target nodes)
    // Vector from source to target
    const dx = targetCenterX - sourceCenterX
    const dy = targetCenterY - sourceCenterY
    const length = Math.sqrt(dx * dx + dy * dy)

    // Perpendicular vector (normalized)
    const perpX = -dy / length
    const perpY = dx / length

    // Apply offset to control points
    const offsetDistance = offset * 50

    // Calculate midpoint
    const midX = (sourceCenterX + targetCenterX) / 2
    const midY = (sourceCenterY + targetCenterY) / 2

    // Apply perpendicular offset to midpoint for control point
    const controlX = midX + perpX * offsetDistance
    const controlY = midY + perpY * offsetDistance

    // Create quadratic bezier path connecting node centers
    const customPath = `M ${sourceCenterX},${sourceCenterY} Q ${controlX},${controlY} ${targetCenterX},${targetCenterY}`

    // Calculate label position at t=0.5 on the bezier curve (midpoint of the curve, not control point)
    // For quadratic bezier: P(t) = (1-t)²·P0 + 2(1-t)t·P1 + t²·P2
    // At t=0.5: P(0.5) = 0.25·P0 + 0.5·P1 + 0.25·P2
    const labelX = 0.25 * sourceCenterX + 0.5 * controlX + 0.25 * targetCenterX
    const labelY = 0.25 * sourceCenterY + 0.5 * controlY + 0.25 * targetCenterY

    return { customPath, labelX, labelY }
  }, [source, target, sourceNode, targetNode, sourceX, sourceY, targetX, targetY, offset])

  return (
    <>
      <path
        id={id}
        style={style}
        className="react-flow__edge-path"
        d={customPath}
        markerEnd={markerEnd}
        fill="none"
      />
      {label && (
        <g>
          <rect
            x={labelX - 20}
            y={labelY - 6.5}
            width={40}
            height={13}
            rx={2}
            fill={labelBgStyle?.fill || "#ffffff"}
            fillOpacity={labelBgStyle?.fillOpacity || 0.9}
            stroke={(labelStyle as any)?.border || "#3b82f6"}
            strokeWidth={0.5}
          />
          <text
            x={labelX}
            y={labelY}
            textAnchor="middle"
            dominantBaseline="middle"
            style={labelStyle}
          >
            {label}
          </text>
        </g>
      )}
    </>
  )
}
