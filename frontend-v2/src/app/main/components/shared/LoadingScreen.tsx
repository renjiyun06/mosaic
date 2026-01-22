/**
 * Loading Screen - Displayed while loading Mosaics
 */

import { Loader2 } from "lucide-react"

export function LoadingScreen() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="text-center">
        <Loader2 className="h-12 w-12 animate-spin text-cyan-400 mx-auto mb-4" />
        <div className="font-mono text-cyan-300">Loading Mosaics...</div>
      </div>
    </div>
  )
}
