"use client"

/**
 * Authentication Context
 * Manages user authentication state and provides auth-related methods
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api'
import type { UserOut, LoginRequest, RegisterRequest, SendCodeRequest } from '@/lib/types'

interface AuthContextType {
  user: UserOut | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
  sendVerificationCode: (data: SendCodeRequest) => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const [user, setUser] = useState<UserOut | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = async () => {
      if (typeof window === 'undefined') return

      const storedToken = localStorage.getItem('auth_token')
      if (!storedToken) {
        setIsLoading(false)
        return
      }

      setToken(storedToken)

      // Verify token by fetching user info
      try {
        const userData = await apiClient.getCurrentUser()
        setUser(userData)
      } catch (error) {
        // Token is invalid, clear it
        console.error('Failed to verify token:', error)
        localStorage.removeItem('auth_token')
        setToken(null)
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [])

  const login = async (data: LoginRequest) => {
    const response = await apiClient.login(data)

    // Save token to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', response.access_token)
    }

    setToken(response.access_token)
    setUser(response.user)
  }

  const register = async (data: RegisterRequest) => {
    const response = await apiClient.register(data)

    // Save token to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', response.access_token)
    }

    setToken(response.access_token)
    setUser(response.user)
  }

  const logout = async () => {
    // Call backend logout
    await apiClient.logout()

    // Clear local state
    setToken(null)
    setUser(null)

    // Redirect to login page
    router.push('/login')
  }

  const sendVerificationCode = async (data: SendCodeRequest) => {
    await apiClient.sendVerificationCode(data)
  }

  const refreshUser = async () => {
    if (!token) return

    try {
      const userData = await apiClient.getCurrentUser()
      setUser(userData)
    } catch (error) {
      console.error('Failed to refresh user:', error)
      // Token might be expired, logout
      await logout()
    }
  }

  const value: AuthContextType = {
    user,
    token,
    isLoading,
    isAuthenticated: !!user && !!token,
    login,
    register,
    logout,
    sendVerificationCode,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
