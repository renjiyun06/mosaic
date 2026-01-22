/**
 * Mosaic management hook - handles CRUD operations and state
 */

import { useState, useEffect } from "react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/contexts/auth-context"
import type { MosaicOut } from "@/lib/types"

export function useMosaicManagement() {
  const { token } = useAuth()
  const [mosaics, setMosaics] = useState<MosaicOut[]>([])
  const [currentMosaicId, setCurrentMosaicId] = useState<number | null>(null)
  const [loadingMosaics, setLoadingMosaics] = useState(true)
  const [createMosaicOpen, setCreateMosaicOpen] = useState(false)
  const [editingMosaic, setEditingMosaic] = useState<MosaicOut | null>(null)

  // Load all Mosaics on mount
  useEffect(() => {
    const fetchMosaics = async () => {
      if (!token) return

      try {
        setLoadingMosaics(true)
        const data = await apiClient.listMosaics()
        setMosaics(data)

        // Auto-select first running Mosaic, or first Mosaic if none running
        if (data.length > 0) {
          const runningMosaic = data.find((m) => m.status === "running")
          setCurrentMosaicId(runningMosaic?.id || data[0].id)
        }
      } catch (error) {
        console.error("Failed to fetch mosaics:", error)
      } finally {
        setLoadingMosaics(false)
      }
    }

    fetchMosaics()
  }, [token])

  // Create new Mosaic
  const handleCreateMosaic = async (name: string, description: string) => {
    if (!token) return

    try {
      await apiClient.createMosaic({ name, description: description || undefined })
      const data = await apiClient.listMosaics()
      setMosaics(data)
      setCreateMosaicOpen(false)
    } catch (error) {
      console.error("Failed to create mosaic:", error)
    }
  }

  // Edit existing Mosaic
  const handleEditMosaic = async (mosaicId: number, name: string, description: string) => {
    if (!token) return

    try {
      await apiClient.updateMosaic(mosaicId, { name, description: description || undefined })
      const data = await apiClient.listMosaics()
      setMosaics(data)
      setEditingMosaic(null)
    } catch (error) {
      console.error("Failed to update mosaic:", error)
    }
  }

  // Delete Mosaic
  const handleDeleteMosaic = async (mosaic: MosaicOut) => {
    if (!token) return
    if (mosaic.node_count > 0) {
      alert("Cannot delete Mosaic with existing nodes. Please delete all nodes first.")
      return
    }

    if (!confirm(`Are you sure you want to delete "${mosaic.name}"? This action cannot be undone.`)) {
      return
    }

    try {
      await apiClient.deleteMosaic(mosaic.id)
      const data = await apiClient.listMosaics()
      setMosaics(data)

      // If deleted current Mosaic, switch to another one
      if (currentMosaicId === mosaic.id) {
        setCurrentMosaicId(data.length > 0 ? data[0].id : null)
      }
    } catch (error) {
      console.error("Failed to delete mosaic:", error)
    }
  }

  // Toggle Mosaic status (start/stop)
  const handleToggleMosaicStatus = async (mosaic: MosaicOut) => {
    if (!token) return

    try {
      if (mosaic.status === "running") {
        await apiClient.stopMosaic(mosaic.id)
      } else {
        await apiClient.startMosaic(mosaic.id)
      }

      const data = await apiClient.listMosaics()
      setMosaics(data)
    } catch (error) {
      console.error("Failed to toggle mosaic status:", error)
    }
  }

  // Switch to different Mosaic
  const handleSwitchMosaic = (mosaicId: number) => {
    setCurrentMosaicId(mosaicId)
  }

  const currentMosaic = mosaics.find((m) => m.id === currentMosaicId) || null

  return {
    mosaics,
    currentMosaicId,
    currentMosaic,
    loadingMosaics,
    createMosaicOpen,
    setCreateMosaicOpen,
    editingMosaic,
    setEditingMosaic,
    handleCreateMosaic,
    handleEditMosaic,
    handleDeleteMosaic,
    handleToggleMosaicStatus,
    handleSwitchMosaic,
  }
}
