"use client"

/**
 * Navigation Bar Component
 * Displays branding, mosaic selector, and user menu
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Boxes, ChevronDown, Settings, LogOut, Menu } from "lucide-react"
import { Button } from "./ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar"
import { useAuth } from "@/contexts/auth-context"
import { apiClient } from "@/lib/api"
import type { MosaicOut } from "@/lib/types"

interface NavbarProps {
  onMenuClick?: () => void
  showMenuButton?: boolean
}

export function Navbar({ onMenuClick, showMenuButton = false }: NavbarProps = {}) {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()
  const [mosaics, setMosaics] = useState<MosaicOut[]>([])

  // Extract mosaic ID and current page from pathname
  const pathMosaicId = pathname.match(/\/mosaic\/(\d+)/)?.[1]
  const currentMosaicId = pathMosaicId ? parseInt(pathMosaicId) : null
  const currentMosaic = mosaics.find((m) => m.id === currentMosaicId)

  // Extract current page type (e.g., "nodes", "connections", "topology")
  const currentPage = pathname.match(/\/mosaic\/\d+\/([^/]+)/)?.[1] || "nodes"

  // Fetch mosaics when user is logged in
  useEffect(() => {
    if (!user) return

    const fetchMosaics = async () => {
      try {
        const data = await apiClient.listMosaics()
        setMosaics(data)
      } catch (error) {
        console.error("Failed to fetch mosaics:", error)
      }
    }

    fetchMosaics()
  }, [user])

  const handleLogout = async () => {
    await logout()
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center px-4">
        {/* Mobile menu button */}
        {showMenuButton && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onMenuClick}
            className="mr-2 lg:hidden"
          >
            <Menu className="h-5 w-5" />
            <span className="sr-only">打开菜单</span>
          </Button>
        )}

        <div className="mr-4 flex items-center">
          <Link href="/" className="flex items-center space-x-2">
            <Boxes className="h-5 w-5 sm:h-6 sm:w-6" />
            <span className="font-bold text-sm sm:text-base">Mosaic</span>
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-end space-x-1 sm:space-x-2">
          {currentMosaic && mosaics.length > 0 && (
            <DropdownMenu modal={false}>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-1 sm:gap-2 text-sm sm:text-base px-2 sm:px-4">
                  <span className="hidden sm:inline">{currentMosaic.name}</span>
                  <span className="sm:hidden truncate max-w-[120px]">{currentMosaic.name}</span>
                  <ChevronDown className="h-3 w-3 sm:h-4 sm:w-4 opacity-50" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-[180px] sm:w-[200px]">
                <DropdownMenuLabel className="text-sm">切换 Mosaic</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {mosaics.map((mosaic) => (
                  <DropdownMenuItem
                    key={mosaic.id}
                    asChild
                    disabled={mosaic.id === currentMosaicId}
                    className="text-sm"
                  >
                    <Link href={`/mosaic/${mosaic.id}/${currentPage}`}>
                      <span className="truncate">{mosaic.name}</span>
                      {mosaic.id === currentMosaicId && <span className="ml-auto">✓</span>}
                    </Link>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild className="text-sm">
                  <Link href="/">查看所有 Mosaic</Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {user && (
            <DropdownMenu modal={false}>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-7 w-7 sm:h-8 sm:w-8 rounded-full hover:ring-1 hover:ring-border">
                  <Avatar className="h-7 w-7 sm:h-8 sm:w-8">
                    <AvatarImage src={user.avatar_url || undefined} alt={user.username} />
                    <AvatarFallback className="text-xs sm:text-sm">{user.username.charAt(0).toUpperCase()}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-48 sm:w-56" align="end" forceMount>
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium leading-none truncate">{user.username}</p>
                    <p className="text-xs leading-none text-muted-foreground truncate">
                      {user.email}
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/user/settings" className="cursor-pointer text-sm">
                    <Settings className="mr-2 h-4 w-4" />
                    <span>账户设置</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-sm">
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>退出登录</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}
