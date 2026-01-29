import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"
import { useTheme } from "@/contexts/theme-context"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const { theme } = useTheme()
    const Comp = asChild ? Slot : "button"

    // Get theme-specific classes
    const getThemeClasses = () => {
      switch (theme) {
        case 'cyberpunk':
          return variant === 'default'
            ? 'neon-border hover:shadow-[0_0_20px_hsl(var(--primary)/0.5)]'
            : variant === 'outline'
            ? 'hover:neon-border'
            : ''
        case 'glassmorphism':
          return variant === 'default' || variant === 'outline'
            ? 'backdrop-blur-md bg-opacity-80'
            : ''
        case 'terminal':
          return variant === 'default'
            ? 'border-2 border-primary hover:shadow-[0_0_12px_hsl(var(--primary))] font-mono'
            : variant === 'outline'
            ? 'border-2 font-mono'
            : 'font-mono'
        case 'minimal':
          return variant === 'default'
            ? 'rounded-none border-2 border-foreground hover:bg-foreground hover:text-background'
            : variant === 'outline'
            ? 'rounded-none border-2'
            : 'rounded-none'
        default:
          return ''
      }
    }

    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }), getThemeClasses())}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
