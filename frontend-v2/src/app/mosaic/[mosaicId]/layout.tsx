"use client"

import { useState } from "react"
import { Navbar } from "@/components/navbar"
import { Sidebar } from "@/components/sidebar"
import { AuthGuard } from "@/components/auth-guard"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { use } from "react"

export default function MosaicLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ mosaicId: string }>
}) {
  const { mosaicId } = use(params)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <AuthGuard>
      <div className="h-full bg-background flex flex-col">
        <Navbar
          showMenuButton={true}
          onMenuClick={() => setMobileMenuOpen(true)}
        />
        <div className="flex flex-1 overflow-hidden">
          {/* Desktop Sidebar */}
          <div className="hidden lg:block">
            <Sidebar mosaicId={mosaicId} />
          </div>

          {/* Mobile Sidebar (Sheet) */}
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetContent side="left" className="p-0 w-64">
              <SheetTitle className="sr-only">导航菜单</SheetTitle>
              <Sidebar mosaicId={mosaicId} onNavigate={() => setMobileMenuOpen(false)} />
            </SheetContent>
          </Sheet>

          <main className="flex-1 overflow-hidden p-4 sm:p-6 relative">{children}</main>
        </div>
      </div>
    </AuthGuard>
  )
}
