import { Navbar } from "@/components/navbar"
import { Sidebar } from "@/components/sidebar"

export default async function MosaicLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ mosaicId: string }>
}) {
  const { mosaicId } = await params

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="flex h-[calc(100vh-3.5rem)]">
        <Sidebar mosaicId={mosaicId} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  )
}
