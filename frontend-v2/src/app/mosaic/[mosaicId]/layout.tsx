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
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex h-[calc(100vh-3.5rem)]">
          <Sidebar mosaicId={mosaicId} />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  )
}
