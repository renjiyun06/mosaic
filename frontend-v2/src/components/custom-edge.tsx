/**
 * Custom edge component with offset support for multiple edges
 */

import { BaseEdge, EdgeLabelRenderer, EdgeProps, getBezierPath } from '@xyflow/react'

export default function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  label,
  labelStyle,
  labelBgStyle,
  data,
}: EdgeProps) {
  const offset = (data?.offset as number) || 0
  const offsetMultiplier = 30 // Distance between parallel edges

  // Calculate perpendicular offset
  const dx = targetX - sourceX
  const dy = targetY - sourceY
  const length = Math.sqrt(dx * dx + dy * dy)

  // Perpendicular vector (rotated 90 degrees)
  const perpX = -dy / length
  const perpY = dx / length

  // Apply offset to control points
  const offsetX = perpX * offset * offsetMultiplier
  const offsetY = perpY * offset * offsetMultiplier

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: sourceX + offsetX,
    sourceY: sourceY + offsetY,
    sourcePosition,
    targetX: targetX + offsetX,
    targetY: targetY + offsetY,
    targetPosition,
    curvature: 0.25 + Math.abs(offset) * 0.1, // More curve for offset edges
  })

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: 12,
              pointerEvents: 'all',
              ...labelStyle,
            }}
            className="nodrag nopan"
          >
            <div
              style={{
                padding: '4px 8px',
                borderRadius: '4px',
                background: '#ffffff',
                border: '1px solid #3b82f6',
                ...labelBgStyle,
              }}
            >
              {label}
            </div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
