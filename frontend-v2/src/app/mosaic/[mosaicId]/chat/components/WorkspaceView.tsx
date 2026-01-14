import { Loader2, Code2 } from "lucide-react"
import type { CodeServerStatus } from "@/lib/types"

interface WorkspaceViewProps {
  sessionId: string
  nodeId: string
  mosaicId: number
  isVisible: boolean
  codeServerStatus: CodeServerStatus
  codeServerUrl: string | null
}

export function WorkspaceView({
  isVisible,
  codeServerStatus,
  codeServerUrl,
}: WorkspaceViewProps) {
  if (!isVisible) {
    return null
  }

  return (
    <div className="flex-1 flex flex-col bg-muted/20 overflow-hidden">
      {codeServerStatus === 'stopped' ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-muted-foreground px-4">
            <Code2 className="h-20 w-20 mx-auto mb-4 opacity-20" />
            <p className="text-lg font-medium mb-2">Code-Server 未启动</p>
            <p className="text-sm text-muted-foreground">
              使用顶部的启动按钮来启动 Code-Server
            </p>
          </div>
        </div>
      ) : codeServerStatus === 'starting' ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-muted-foreground px-4">
            <Loader2 className="h-20 w-20 mx-auto mb-4 animate-spin" />
            <p className="text-lg font-medium">正在启动 Code-Server...</p>
            <p className="text-sm text-muted-foreground mt-2">
              请稍候，这可能需要几秒钟
            </p>
          </div>
        </div>
      ) : codeServerUrl ? (
        <iframe
          src={codeServerUrl}
          className="w-full h-full border-0"
          title="Code-Server"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-muted-foreground px-4">
            <Code2 className="h-20 w-20 mx-auto mb-4 opacity-20" />
            <p className="text-lg font-medium">Code-Server 地址不可用</p>
            <p className="text-sm text-muted-foreground mt-2">
              请尝试重新启动 Code-Server
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
