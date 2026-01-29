'use client'

import { useState, useEffect } from 'react'
import { apiClient } from '@/lib/api'
import type { MosaicOut, NodeOut } from '@/lib/types'
import { MosaicStatus, NodeStatus } from '@/lib/types'

interface NodeSelectorProps {
  onNodeSelect?: (mosaicId: number, nodeId: string) => void
}

export function NodeSelector({ onNodeSelect }: NodeSelectorProps) {
  const [mosaics, setMosaics] = useState<MosaicOut[]>([])
  const [nodes, setNodes] = useState<NodeOut[]>([])
  const [selectedMosaicId, setSelectedMosaicId] = useState<number | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch mosaics on component mount
  useEffect(() => {
    fetchMosaics()
  }, [])

  // Fetch nodes when mosaic is selected
  useEffect(() => {
    if (selectedMosaicId !== null) {
      fetchNodes(selectedMosaicId)
    } else {
      setNodes([])
      setSelectedNodeId(null)
    }
  }, [selectedMosaicId])

  const fetchMosaics = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.listMosaics()
      setMosaics(data)

      // Auto-select first running mosaic
      const firstRunning = data.find(m => m.status === MosaicStatus.RUNNING)
      if (firstRunning) {
        setSelectedMosaicId(firstRunning.id)
      }
    } catch (err) {
      setError('Failed to load mosaics')
      console.error('Error fetching mosaics:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchNodes = async (mosaicId: number) => {
    try {
      setError(null)
      const data = await apiClient.listNodes(mosaicId)
      setNodes(data)

      // Auto-select first running node
      const firstRunning = data.find(n => n.status === NodeStatus.RUNNING)
      if (firstRunning) {
        setSelectedNodeId(firstRunning.node_id)
        onNodeSelect?.(mosaicId, firstRunning.node_id)
      }
    } catch (err) {
      setError('Failed to load nodes')
      console.error('Error fetching nodes:', err)
    }
  }

  const handleMosaicChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const mosaicId = e.target.value ? parseInt(e.target.value) : null
    setSelectedMosaicId(mosaicId)
    setSelectedNodeId(null)
  }

  const handleNodeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nodeId = e.target.value || null
    setSelectedNodeId(nodeId)

    if (nodeId && selectedMosaicId) {
      onNodeSelect?.(selectedMosaicId, nodeId)
    }
  }

  const getMosaicStatusIcon = (status: MosaicStatus) => {
    switch (status) {
      case MosaicStatus.RUNNING:
        return '✅'
      case MosaicStatus.STOPPED:
        return '⚪'
      case MosaicStatus.STARTING:
        return '🔄'
      default:
        return '⚪'
    }
  }

  const getNodeStatusIcon = (status: NodeStatus) => {
    switch (status) {
      case NodeStatus.RUNNING:
        return '✅'
      case NodeStatus.STOPPED:
        return '⚪'
      default:
        return '⚪'
    }
  }

  if (loading) {
    return (
      <div className="text-[10px] text-muted-foreground">
        Loading...
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-[10px] text-destructive">
        Error
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1">
      {/* Mosaic Selector */}
      <select
        value={selectedMosaicId || ''}
        onChange={handleMosaicChange}
        className="text-[10px] border rounded px-1.5 py-0.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring max-w-[80px] truncate"
        title={mosaics.find(m => m.id === selectedMosaicId)?.name || 'Select Instance'}
      >
        <option value="">Instance</option>
        {mosaics.map((mosaic) => {
          const isRunning = mosaic.status === MosaicStatus.RUNNING

          return (
            <option
              key={mosaic.id}
              value={mosaic.id}
              disabled={!isRunning}
              className={isRunning ? 'text-foreground' : 'text-muted-foreground'}
            >
              {mosaic.name}
            </option>
          )
        })}
      </select>

      {/* Arrow separator */}
      {selectedMosaicId && (
        <span className="text-muted-foreground text-[10px]">→</span>
      )}

      {/* Node Selector */}
      {selectedMosaicId && (
        <select
          value={selectedNodeId || ''}
          onChange={handleNodeChange}
          className="text-[10px] border rounded px-1.5 py-0.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring max-w-[100px] truncate"
          title={nodes.find(n => n.node_id === selectedNodeId)?.node_id || 'Select Node'}
        >
          <option value="">Node</option>
          {nodes.map((node) => {
            const isRunning = node.status === NodeStatus.RUNNING

            return (
              <option
                key={node.node_id}
                value={node.node_id}
                disabled={!isRunning}
                className={isRunning ? 'text-foreground' : 'text-muted-foreground'}
              >
                {node.node_id}
              </option>
            )
          })}
        </select>
      )}
    </div>
  )
}
