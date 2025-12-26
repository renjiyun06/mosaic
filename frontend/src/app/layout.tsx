import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthGuard } from "@/components/auth-guard";
import { WebSocketProvider } from "@/components/websocket-provider";
import { DialogProvider } from "@/components/dialogs/dialog-provider";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Mosaic - Event-Driven Multi-Agent System",
  description: "A framework for building distributed multi-agent systems through event mesh",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider
          defaultTheme="light"
          storageKey="mosaic-ui-theme"
        >
          <DialogProvider>
            <AuthGuard>
              <WebSocketProvider>
                {children}
              </WebSocketProvider>
            </AuthGuard>
            <Toaster />
          </DialogProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
