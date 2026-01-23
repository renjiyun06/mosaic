"use client"

import { useCallback } from "react"
import { soundEffects } from "../utils/soundEffects"

/**
 * Hook for playing cyberpunk sound effects
 * Provides callbacks for message and button interactions
 */
export function useSoundEffects() {
  /**
   * Play whoosh sound when message is sent
   */
  const playMessageSent = useCallback(() => {
    soundEffects.playWhoosh()
  }, [])

  /**
   * Play click sound when button is pressed
   */
  const playButtonClick = useCallback(() => {
    soundEffects.playClick()
  }, [])

  /**
   * Play result sound when agent reply is completed
   */
  const playResultReceived = useCallback(() => {
    soundEffects.playResult()
  }, [])

  /**
   * Enable or disable sound effects
   */
  const setEnabled = useCallback((enabled: boolean) => {
    soundEffects.setEnabled(enabled)
  }, [])

  /**
   * Set volume (0.0 - 1.0)
   */
  const setVolume = useCallback((volume: number) => {
    soundEffects.setVolume(volume)
  }, [])

  return {
    playMessageSent,
    playButtonClick,
    playResultReceived,
    setEnabled,
    setVolume,
    isEnabled: soundEffects.isEnabled(),
    volume: soundEffects.getVolume(),
  }
}
