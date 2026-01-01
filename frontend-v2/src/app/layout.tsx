import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import "./globals.css"
import { NotificationProvider } from "@/components/providers/notification-provider"
import { AuthProvider } from "@/contexts/auth-context"
import { WebSocketProvider } from "@/contexts/websocket-context"
import { Toaster } from "@/components/ui/toaster"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Mosaic - Event-Driven Multi-Agent System",
  description: "Event-driven distributed multi-agent system",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <WebSocketProvider>
            <NotificationProvider>
              {children}
              <Toaster />
            </NotificationProvider>
          </WebSocketProvider>
        </AuthProvider>
      </body>
    </html>
  )
}
