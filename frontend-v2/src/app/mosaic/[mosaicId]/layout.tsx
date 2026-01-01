"use client"

import { Navbar } from "@/components/navbar"
import { Sidebar } from "@/components/sidebar"
import { AuthGuard } from "@/components/auth-guard"
import { use } from "react"

export default function MosaicLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ mosaicId: string }>
}) {
  const { mosaicId } = use(params)

  return (
    <AuthGuard>
      <div className="h-full bg-background flex flex-col">
        <Navbar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar mosaicId={mosaicId} />
          <main className="flex-1 overflow-hidden p-6 relative">{children}</main>
        </div>
      </div>
    </AuthGuard>
  )
}
