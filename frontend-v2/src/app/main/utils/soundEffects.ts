/**
 * Cyberpunk sound effects using Web Audio API
 * Generates sci-fi whoosh and click sounds for message interactions
 */

class SoundEffects {
  private audioContext: AudioContext | null = null
  private enabled: boolean = true
  private volume: number = 0.3
  private lastPlayTime: number = 0
  private readonly MIN_INTERVAL = 200 // Prevent rapid fire (ms)

  constructor() {
    // Check if reduced motion is preferred (accessibility)
    if (typeof window !== "undefined") {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        this.enabled = false
      }
    }
  }

  /**
   * Get or create AudioContext instance
   */
  private getAudioContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext ||
        (window as any).webkitAudioContext)()
    }
    return this.audioContext
  }

  /**
   * Play whoosh sound (message sent)
   * Frequency sweep: 800Hz -> 200Hz over 150ms
   * Creates a sci-fi "swoosh" effect
   */
  playWhoosh(): void {
    if (!this.enabled) return

    const now = Date.now()
    if (now - this.lastPlayTime < this.MIN_INTERVAL) return
    this.lastPlayTime = now

    try {
      const ctx = this.getAudioContext()
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)

      // Whoosh: frequency sweep 800Hz -> 200Hz
      oscillator.frequency.setValueAtTime(800, ctx.currentTime)
      oscillator.frequency.exponentialRampToValueAtTime(
        200,
        ctx.currentTime + 0.15
      )

      // Volume envelope (fade out)
      gainNode.gain.setValueAtTime(this.volume, ctx.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15)

      oscillator.start(ctx.currentTime)
      oscillator.stop(ctx.currentTime + 0.15)
    } catch (error) {
      console.warn("Failed to play whoosh sound:", error)
    }
  }

  /**
   * Play digital click (button press)
   * Short 1200Hz tone over 50ms
   * Creates a crisp click effect
   */
  playClick(): void {
    if (!this.enabled) return

    try {
      const ctx = this.getAudioContext()
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)

      // High-pitched click
      oscillator.frequency.value = 1200

      // Softer volume for click (50% of whoosh)
      gainNode.gain.setValueAtTime(this.volume * 0.5, ctx.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05)

      oscillator.start(ctx.currentTime)
      oscillator.stop(ctx.currentTime + 0.05)
    } catch (error) {
      console.warn("Failed to play click sound:", error)
    }
  }

  /**
   * Enable or disable sound effects
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled
  }

  /**
   * Set volume (0.0 - 1.0)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume))
  }

  /**
   * Check if sound effects are enabled
   */
  isEnabled(): boolean {
    return this.enabled
  }

  /**
   * Get current volume
   */
  getVolume(): number {
    return this.volume
  }
}

// Singleton instance
export const soundEffects = new SoundEffects()
