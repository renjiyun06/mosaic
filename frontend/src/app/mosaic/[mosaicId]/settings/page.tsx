"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Download, Upload, Trash2, Loader2 } from "lucide-react"
import { apiClient, type MosaicResponse } from "@/lib/api"
import { useAuthStore } from "@/lib/store"

export default function SettingsPage() {
  const params = useParams()
  const router = useRouter()
  const { token } = useAuthStore()
  const mosaicId = params.mosaicId as string

  const [mosaic, setMosaic] = useState<MosaicResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch mosaic data
  useEffect(() => {
    if (!token) {
      router.push("/login")
      return
    }

    const fetchMosaic = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await apiClient.getMosaic(Number(mosaicId), token)
        setMosaic(data)
      } catch (err) {
        console.error("Failed to fetch mosaic:", err)
        setError(err instanceof Error ? err.message : "Failed to load mosaic")
      } finally {
        setLoading(false)
      }
    }

    fetchMosaic()
  }, [mosaicId, token, router])

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (error || !mosaic) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground mb-4">
          {error || "Mosaic not found"}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">设置</h1>
        <p className="text-muted-foreground mt-1">管理 Mosaic 实例配置</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
          <CardDescription>修改 Mosaic 实例的基本信息</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">名称</Label>
            <Input id="name" defaultValue={mosaic.name} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">描述</Label>
            <Input id="description" defaultValue={mosaic.description || ""} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mosaicId">Mosaic ID</Label>
            <Input id="mosaicId" value={mosaic.id} disabled />
          </div>
          <Button>保存更改</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据管理</CardTitle>
          <CardDescription>导出、导入或备份 Mosaic 数据</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button variant="outline" className="w-full justify-start">
            <Download className="mr-2 h-4 w-4" />
            导出 Mosaic 数据
          </Button>
          <Button variant="outline" className="w-full justify-start">
            <Upload className="mr-2 h-4 w-4" />
            导入 Mosaic 数据
          </Button>
          <Button variant="outline" className="w-full justify-start">
            <Download className="mr-2 h-4 w-4" />
            创建备份
          </Button>
        </CardContent>
      </Card>

      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">危险区域</CardTitle>
          <CardDescription>这些操作不可逆，请谨慎操作</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button variant="destructive" className="w-full justify-start">
            <Trash2 className="mr-2 h-4 w-4" />
            清空所有数据
          </Button>
          <Button variant="destructive" className="w-full justify-start">
            <Trash2 className="mr-2 h-4 w-4" />
            删除 Mosaic 实例
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
