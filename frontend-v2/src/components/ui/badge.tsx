import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"
import { useTheme } from "@/contexts/theme-context"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  const { theme } = useTheme()

  const getThemeClasses = () => {
    switch (theme) {
      case 'cyberpunk':
        return variant === 'default'
          ? 'border border-primary shadow-[0_0_8px_hsl(var(--primary)/0.4)]'
          : variant === 'outline'
          ? 'border-primary/50'
          : ''
      case 'glassmorphism':
        return variant === 'default' || variant === 'outline'
          ? 'backdrop-blur-sm bg-opacity-70'
          : ''
      case 'terminal':
        return variant === 'default'
          ? 'border border-primary font-mono rounded-none'
          : variant === 'outline'
          ? 'border-primary font-mono rounded-none'
          : 'font-mono rounded-none'
      case 'minimal':
        return variant === 'default'
          ? 'rounded-none border-2 border-foreground'
          : variant === 'outline'
          ? 'rounded-none border-2'
          : 'rounded-none'
      default:
        return ''
    }
  }

  return (
    <div className={cn(badgeVariants({ variant }), getThemeClasses(), className)} {...props} />
  )
}

export { Badge, badgeVariants }
