"use client"

/**
 * Theme Switcher Component
 * Displays a dropdown menu to switch between available themes
 */

import { Palette, Check } from "lucide-react"
import { Button } from "./ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu"
import { useTheme } from "@/contexts/theme-context"

export function ThemeSwitcher() {
  const { theme, setTheme, themes } = useTheme()

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 relative hover:bg-accent"
          title="切换主题"
        >
          <Palette className="h-4 w-4" />
          <span className="sr-only">切换主题</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>选择主题</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {themes.map((t) => (
          <DropdownMenuItem
            key={t.id}
            onClick={() => setTheme(t.id)}
            className="cursor-pointer flex items-center gap-3 py-3"
          >
            {/* Theme preview circle */}
            <div
              className="w-8 h-8 rounded-full border-2 border-border flex-shrink-0"
              style={{
                background: t.preview,
              }}
            />

            {/* Theme info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{t.name}</span>
                {theme === t.id && (
                  <Check className="h-4 w-4 text-primary" />
                )}
              </div>
              <p className="text-xs text-muted-foreground truncate">
                {t.description}
              </p>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
