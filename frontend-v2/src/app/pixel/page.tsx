"use client"

/**
 * Pixel Game View - Main Page Entry
 * A pixel art game-style visualization of the Mosaic network
 */

import { PixelCanvas } from "./components/PixelCanvas"

export default function PixelPage() {
  return (
    <div className="w-screen h-screen overflow-hidden bg-black">
      <PixelCanvas />
    </div>
  )
}
