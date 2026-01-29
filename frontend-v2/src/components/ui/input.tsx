import * as React from "react"

import { cn } from "@/lib/utils"
import { useTheme } from "@/contexts/theme-context"

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    const { theme } = useTheme()

    const getThemeClasses = () => {
      const baseClasses = "flex h-9 w-full px-3 py-1 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"

      switch (theme) {
        case 'cyberpunk':
          return `${baseClasses} rounded-md border border-primary/30 bg-card/50 focus-visible:border-primary focus-visible:shadow-[0_0_8px_hsl(var(--primary)/0.3)]`
        case 'glassmorphism':
          return `${baseClasses} rounded-md border border-border/50 glass-card focus-visible:ring-1 focus-visible:ring-ring`
        case 'terminal':
          return `${baseClasses} rounded-none border-2 border-primary bg-black/80 font-mono focus-visible:shadow-[0_0_8px_hsl(var(--primary))]`
        case 'minimal':
          return `${baseClasses} rounded-none border-2 border-foreground/30 bg-transparent focus-visible:border-foreground`
        default:
          return `${baseClasses} rounded-md border border-input bg-transparent focus-visible:ring-1 focus-visible:ring-ring`
      }
    }

    return (
      <input
        type={type}
        className={cn(getThemeClasses(), className)}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
