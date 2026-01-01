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
  }, [sourceNode, targetNode, sourceX, sourceY, targetX, targetY, offset])

  return (
    <>
      <path
        id={id}
        style={style}
        className="react-flow__edge-path"
        d={customPath}
        markerEnd={markerEnd}
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
