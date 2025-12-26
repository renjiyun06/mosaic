/**
 * File content preview component
 */
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { FileText, AlertCircle } from "lucide-react"

interface FilePreviewProps {
  fileName: string
  content: string
  mimeType: string
  size: number
  isTruncated: boolean
}

export function FilePreview({
  fileName,
  content,
  mimeType,
  size,
  isTruncated,
}: FilePreviewProps) {
  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Detect if it's a code file
  const isCodeFile = mimeType.includes("javascript") ||
    mimeType.includes("typescript") ||
    mimeType.includes("python") ||
    mimeType.includes("json") ||
    mimeType.includes("html") ||
    mimeType.includes("css") ||
    fileName.endsWith(".ts") ||
    fileName.endsWith(".tsx") ||
    fileName.endsWith(".js") ||
    fileName.endsWith(".jsx") ||
    fileName.endsWith(".py") ||
    fileName.endsWith(".json") ||
    fileName.endsWith(".md") ||
    fileName.endsWith(".txt") ||
    fileName.endsWith(".yaml") ||
    fileName.endsWith(".yml") ||
    fileName.endsWith(".toml")

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b bg-muted/50 flex items-center gap-2">
        <FileText className="h-4 w-4" />
        <span className="font-medium text-sm truncate flex-1">{fileName}</span>
        <Badge variant="outline" className="text-xs">
          {formatSize(size)}
        </Badge>
      </div>

      {/* Truncation warning */}
      {isTruncated && (
        <Alert className="m-3 mb-0">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs">
            File is too large. Showing first 1 MB only.
          </AlertDescription>
        </Alert>
      )}

      {/* Content */}
      <ScrollArea className="flex-1 p-3">
        {isCodeFile ? (
          <pre className="text-xs font-mono whitespace-pre-wrap break-words bg-muted/30 p-3 rounded">
            <code>{content}</code>
          </pre>
        ) : (
          <div className="text-sm whitespace-pre-wrap break-words">
            {content}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
