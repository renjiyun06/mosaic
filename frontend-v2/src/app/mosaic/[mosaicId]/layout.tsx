"use client"

import { useState, useEffect } from "react"
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(256) // Default width: 256px (w-64)
  const [isInitialized, setIsInitialized] = useState(false)

  // Load sidebar state from localStorage
  useEffect(() => {
    const savedCollapsed = localStorage.getItem('sidebar-collapsed')
    const savedWidth = localStorage.getItem('sidebar-width')

    if (savedCollapsed !== null) {
      setSidebarCollapsed(savedCollapsed === 'true')
    }
    if (savedWidth !== null) {
      setSidebarWidth(parseInt(savedWidth, 10))
    }
    setIsInitialized(true)
  }, [])

  // Handle sidebar collapse/expand toggle
  const handleToggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const newValue = !prev
      localStorage.setItem('sidebar-collapsed', String(newValue))
      return newValue
    })
  }

  // Handle sidebar width change
  const handleWidthChange = (width: number) => {
    setSidebarWidth(width)
    localStorage.setItem('sidebar-width', String(width))
  }

  return (
    <AuthGuard>
      <div className="h-full bg-background flex flex-col">
        <Navbar
          showMenuButton={true}
          onMenuClick={() => setMobileMenuOpen(true)}
          sidebarWidth={sidebarWidth}
          sidebarCollapsed={sidebarCollapsed}
        />
        <div className="flex flex-1 overflow-hidden">
          {/* Desktop Sidebar */}
          <div className="hidden lg:block h-full">
            <Sidebar
              mosaicId={mosaicId}
              collapsed={sidebarCollapsed}
              onToggle={handleToggleSidebar}
              width={sidebarWidth}
              onWidthChange={handleWidthChange}
            />
          </div>

          {/* Mobile Sidebar (Sheet) */}
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetContent side="left" className="p-0 w-64" showClose={false}>
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
