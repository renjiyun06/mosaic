"use client"

import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"
import { useAuthStore } from "@/lib/store"

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const isHydrated = useAuthStore((state) => state.isHydrated)

  // 公开页面列表(无需登录即可访问)
  const publicPaths = ["/login", "/register"]
  const isPublicPath = publicPaths.includes(pathname)

  useEffect(() => {
    // Wait for hydration to complete before checking authentication
    if (!isHydrated) return

    // 如果未登录且不在公开页面,重定向到登录页
    if (!isAuthenticated && !isPublicPath) {
      router.push("/login")
    }
    // 如果已登录且在公开页面,重定向到首页
    if (isAuthenticated && isPublicPath) {
      router.push("/")
    }
  }, [isHydrated, isAuthenticated, pathname, isPublicPath, router])

  // Wait for hydration to complete
  if (!isHydrated) {
    return null
  }

  // 如果未登录且不在公开页面,不渲染任何内容
  if (!isAuthenticated && !isPublicPath) {
    return null
  }

  // 如果已登录且在公开页面,不渲染任何内容(等待重定向)
  if (isAuthenticated && isPublicPath) {
    return null
  }

  return <>{children}</>
}
