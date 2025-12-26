'use client'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { cn } from '@/lib/utils'
import { DialogVariant } from '@/lib/dialog-types'

interface AlertDialogInfoProps {
  title: string
  description: string | React.ReactNode
  variant?: DialogVariant
  actionText?: string
  onAction?: () => void
  onClose: () => void
}

const variantStyles: Record<DialogVariant, string> = {
  info: 'bg-blue-600 text-white hover:bg-blue-700',
  warning: 'bg-amber-600 text-white hover:bg-amber-700',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  success: 'bg-green-600 text-white hover:bg-green-700',
}

export function AlertDialogInfo({
  title,
  description,
  variant = 'info',
  actionText = '确定',
  onAction,
  onClose,
}: AlertDialogInfoProps) {
  const handleAction = () => {
    onAction?.()
    onClose()
  }

  return (
    <AlertDialog open onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            {typeof description === 'string' ? <p>{description}</p> : <div>{description}</div>}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction
            onClick={handleAction}
            className={cn(variantStyles[variant])}
          >
            {actionText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
