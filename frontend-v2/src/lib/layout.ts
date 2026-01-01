/**
 * Layout helper for React Flow using dagre
 */

import dagre from 'dagre'
import type { Node, Edge } from '@xyflow/react'

const dagreGraph = new dagre.graphlib.Graph()
dagreGraph.setDefaultEdgeLabel(() => ({}))

/**
 * Calculate node positions using dagre hierarchical layout
 */
export function getLayoutedNodes(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'LR'
): Node[] {
  const nodeWidth = 100
  const nodeHeight = 35

  dagreGraph.setGraph({
    rankdir: direction,
    ranksep: 150,  // Horizontal spacing between ranks
    nodesep: 100,   // Vertical spacing between nodes in same rank
  })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    }
  })
}
