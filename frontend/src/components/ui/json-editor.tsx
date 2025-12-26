"use client"

import { useRef, useEffect, useState } from "react"
import Editor, { OnMount } from "@monaco-editor/react"
import { Button } from "@/components/ui/button"
import { FileJson } from "lucide-react"
import { useTheme } from "@/components/theme-provider"

interface JsonEditorProps {
  value: string
  onChange: (value: string) => void
  height?: string
  readOnly?: boolean
}

export function JsonEditor({ value, onChange, height = "200px", readOnly = false }: JsonEditorProps) {
  const editorRef = useRef<any>(null)
  const { theme } = useTheme()
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("dark")

  // Resolve theme (handle "system" preference)
  useEffect(() => {
    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      setResolvedTheme(systemTheme)

      // Listen for system theme changes
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
      const listener = (e: MediaQueryListEvent) => {
        setResolvedTheme(e.matches ? "dark" : "light")
      }
      mediaQuery.addEventListener("change", listener)
      return () => mediaQuery.removeEventListener("change", listener)
    } else {
      setResolvedTheme(theme)
    }
  }, [theme])

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor
  }

  const formatJson = () => {
    if (editorRef.current) {
      editorRef.current.getAction("editor.action.formatDocument").run()
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">JSON 配置</p>
        {!readOnly && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={formatJson}
            className="h-7"
          >
            <FileJson className="h-3.5 w-3.5 mr-1.5" />
            格式化
          </Button>
        )}
      </div>
      <div className="border rounded-md overflow-hidden">
        <Editor
          height={height}
          defaultLanguage="json"
          value={value}
          onChange={(value) => onChange(value || "{}")}
          onMount={handleEditorDidMount}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            readOnly,
            wordWrap: "on",
            formatOnPaste: true,
            formatOnType: true,
          }}
          theme={resolvedTheme === "dark" ? "vs-dark" : "light"}
        />
      </div>
    </div>
  )
}
