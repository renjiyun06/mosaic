"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useAuthStore } from "@/lib/store"
import { AlertCircle, CheckCircle, Mail } from "lucide-react"

export default function RegisterPage() {
  const router = useRouter()
  const { register, sendVerificationCode } = useAuthStore()

  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [verificationCode, setVerificationCode] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  // Verification code states
  const [codeSent, setCodeSent] = useState(false)
  const [sendingCode, setSendingCode] = useState(false)
  const [countdown, setCountdown] = useState(0)

  // Countdown timer effect
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [countdown])

  // Send verification code
  const handleSendCode = async () => {
    if (!email.trim() || sendingCode || countdown > 0) return

    // Email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setError("请输入有效的邮箱地址")
      return
    }

    setSendingCode(true)
    setError("")

    const result = await sendVerificationCode(email.trim())

    if (result.success) {
      setCodeSent(true)
      setCountdown(60)
    } else {
      setError(result.message || "发送验证码失败")
    }

    setSendingCode(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    // Input validation
    if (!username.trim()) {
      setError("请输入用户名")
      return
    }

    if (!email.trim()) {
      setError("请输入邮箱")
      return
    }

    // Email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setError("请输入有效的邮箱地址")
      return
    }

    if (!password) {
      setError("请输入密码")
      return
    }

    if (password.length < 8) {
      setError("密码长度至少为 8 个字符")
      return
    }

    if (password !== confirmPassword) {
      setError("两次输入的密码不一致")
      return
    }

    if (!verificationCode.trim()) {
      setError("请输入验证码")
      return
    }

    if (verificationCode.length !== 6) {
      setError("验证码为 6 位数字")
      return
    }

    setIsLoading(true)

    const result = await register(
      username.trim(),
      email.trim(),
      password,
      verificationCode.trim()
    )

    if (result.success) {
      // Registration successful, redirect to login page
      router.push("/login?registered=true")
    } else {
      setError(result.message || "注册失败,请稍后重试")
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">创建账户</CardTitle>
          <CardDescription className="text-center">
            填写以下信息以创建您的 Mosaic 账户
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                type="text"
                placeholder="输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">邮箱</Label>
              <div className="flex gap-2">
                <Input
                  id="email"
                  type="email"
                  placeholder="输入邮箱地址"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading || sendingCode}
                  required
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSendCode}
                  disabled={
                    isLoading || sendingCode || countdown > 0 || !email.trim()
                  }
                  className="whitespace-nowrap"
                >
                  {sendingCode ? (
                    "发送中..."
                  ) : countdown > 0 ? (
                    `${countdown}s`
                  ) : codeSent ? (
                    "重新发送"
                  ) : (
                    <>
                      <Mail className="h-4 w-4 mr-1" />
                      发送验证码
                    </>
                  )}
                </Button>
              </div>
              {codeSent && countdown > 0 && (
                <p className="text-xs text-muted-foreground">
                  验证码已发送至您的邮箱，请查收
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="verification-code">验证码</Label>
              <Input
                id="verification-code"
                type="text"
                placeholder="输入 6 位验证码"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value)}
                disabled={isLoading}
                maxLength={6}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                placeholder="输入密码 (至少 8 个字符)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm-password">确认密码</Label>
              <Input
                id="confirm-password"
                type="password"
                placeholder="再次输入密码"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                <AlertCircle className="h-4 w-4" />
                <span>{error}</span>
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "注册中..." : "注册"}
            </Button>

            <div className="text-center text-sm text-muted-foreground">
              已有账户?{" "}
              <Link href="/login" className="text-primary hover:underline font-medium">
                立即登录
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
