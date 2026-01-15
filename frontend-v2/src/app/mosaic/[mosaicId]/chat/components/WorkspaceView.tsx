import { Loader2, Code2 } from "lucide-react"

interface WorkspaceViewProps {
  sessionId: string
  nodeId: string
  mosaicId: number
  isVisible: boolean
  codeServerUrl: string | null
}

export function WorkspaceView({
  isVisible,
  codeServerUrl,
}: WorkspaceViewProps) {
  if (!isVisible) {
    return null
  }

  return (
    <div className="flex-1 flex flex-col bg-muted/20 overflow-hidden">
      {codeServerUrl ? (
        <iframe
          src={codeServerUrl}
          className="w-full h-full border-0"
          title="Code-Server"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-muted-foreground px-4">
            <Loader2 className="h-20 w-20 mx-auto mb-4 animate-spin" />
            <p className="text-lg font-medium">正在加载工作区...</p>
            <p className="text-sm text-muted-foreground mt-2">
              请稍候
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
