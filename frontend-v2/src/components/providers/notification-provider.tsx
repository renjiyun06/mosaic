"use client"

import { createContext, useContext, ReactNode, useEffect } from 'react'
import { toast } from '@/hooks/use-toast'
import { setToastNotification } from '@/lib/request'

// ==================== Context Value ====================

interface NotificationContextValue {
  // Toast shortcuts
  toast: {
    success: (message: string) => void
    error: (message: string) => void
    warning: (message: string) => void
    info: (message: string) => void
  }
}

const NotificationContext = createContext<NotificationContextValue | null>(null)

// ==================== Provider ====================

export function NotificationProvider({ children }: { children: ReactNode }) {
  // Initialize toast notification functions for request.ts
  useEffect(() => {
    setToastNotification({
      success: (message: string) => {
        toast({
          title: '操作成功',
          description: message,
        })
      },
      error: (message: string) => {
        toast({
          variant: 'destructive',
          title: '操作失败',
          description: message,
        })
      }
    })
  }, [])

  const value: NotificationContextValue = {
    toast: {
      success: (message: string) => {
        toast({
          title: '操作成功',
          description: message,
        })
      },
      error: (message: string) => {
        toast({
          variant: 'destructive',
          title: '操作失败',
          description: message,
        })
      },
      warning: (message: string) => {
        toast({
          variant: 'destructive',
          title: '警告',
          description: message,
        })
      },
      info: (message: string) => {
        toast({
          title: '提示',
          description: message,
        })
      }
    }
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}

// ==================== Hook ====================

/**
 * Use notification system
 *
 * @example
 * const { toast } = useNotification()
 *
 * // Show success toast
 * toast.success('操作成功')
 *
 * // Show error toast
 * toast.error('操作失败')
 */
export function useNotification() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotification must be used within NotificationProvider')
  }
  return context
}
