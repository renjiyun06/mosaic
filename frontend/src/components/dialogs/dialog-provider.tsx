'use client'

import { createContext, useState, useCallback, ReactNode } from 'react'
import { ConfirmDialog } from './confirm-dialog'
import { AlertDialogInfo } from './alert-dialog-info'
import { useToast } from '@/hooks/use-toast'
import { ConfirmDialogOptions, AlertDialogOptions } from '@/lib/dialog-types'

interface DialogContextValue {
  // Confirmation dialog
  confirm: (options: ConfirmDialogOptions) => void

  // Alert dialog
  alert: (options: AlertDialogOptions) => void

  // Toast shortcuts
  showError: (message: string, title?: string) => void
  showSuccess: (message: string, title?: string) => void
  showWarning: (message: string, title?: string) => void
  showInfo: (message: string, title?: string) => void
}

export const DialogContext = createContext<DialogContextValue | null>(null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const { toast } = useToast()
  const [confirmOptions, setConfirmOptions] = useState<ConfirmDialogOptions | null>(null)
  const [alertOptions, setAlertOptions] = useState<AlertDialogOptions | null>(null)

  const confirm = useCallback((options: ConfirmDialogOptions) => {
    setConfirmOptions(options)
  }, [])

  const alert = useCallback((options: AlertDialogOptions) => {
    setAlertOptions(options)
  }, [])

  const showError = useCallback((message: string, title = '操作失败') => {
    toast({
      variant: 'destructive',
      title,
      description: message,
    })
  }, [toast])

  const showSuccess = useCallback((message: string, title = '操作成功') => {
    toast({
      title,
      description: message,
    })
  }, [toast])

  const showWarning = useCallback((message: string, title = '警告') => {
    toast({
      title,
      description: message,
      variant: 'destructive', // Use destructive variant for warning
    })
  }, [toast])

  const showInfo = useCallback((message: string, title = '提示') => {
    toast({
      title,
      description: message,
    })
  }, [toast])

  return (
    <DialogContext.Provider
      value={{ confirm, alert, showError, showSuccess, showWarning, showInfo }}
    >
      {children}

      {/* Global confirmation dialog */}
      {confirmOptions && (
        <ConfirmDialog
          {...confirmOptions}
          onClose={() => setConfirmOptions(null)}
        />
      )}

      {/* Global alert dialog */}
      {alertOptions && (
        <AlertDialogInfo
          {...alertOptions}
          onClose={() => setAlertOptions(null)}
        />
      )}
    </DialogContext.Provider>
  )
}
