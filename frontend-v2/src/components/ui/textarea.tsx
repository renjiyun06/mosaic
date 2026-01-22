import * as React from "react"

import { cn } from "@/lib/utils"
import { useTheme } from "@/contexts/theme-context"

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    const { theme } = useTheme()

    const getThemeClasses = () => {
      const baseClasses = "flex min-h-[80px] w-full px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"

      switch (theme) {
        case 'cyberpunk':
          return `${baseClasses} rounded-md border border-primary/30 bg-card/50 focus-visible:border-primary focus-visible:shadow-[0_0_8px_hsl(var(--primary)/0.3)] ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`
        case 'glassmorphism':
          return `${baseClasses} rounded-md border border-border/50 glass-card ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`
        case 'terminal':
          return `${baseClasses} rounded-none border-2 border-primary bg-black/80 font-mono focus-visible:shadow-[0_0_8px_hsl(var(--primary))] focus-visible:ring-0`
        case 'minimal':
          return `${baseClasses} rounded-none border-2 border-foreground/30 bg-background focus-visible:border-foreground focus-visible:ring-0`
        default:
          return `${baseClasses} rounded-md border border-input bg-background ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`
      }
    }

    return (
      <textarea
        className={cn(getThemeClasses(), className)}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
