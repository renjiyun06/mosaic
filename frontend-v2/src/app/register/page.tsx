"use client"

/**
 * Register Page
 * Allows users to create a new account with email verification
 */

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
import { useAuth } from "@/contexts/auth-context"
import { Mail } from "lucide-react"

export default function RegisterPage() {
  const router = useRouter()
  const { register, sendVerificationCode, isAuthenticated } = useAuth()

  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [verificationCode, setVerificationCode] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  // Verification code states
  const [codeSent, setCodeSent] = useState(false)
  const [sendingCode, setSendingCode] = useState(false)
  const [countdown, setCountdown] = useState(0)

  // Client-side validation error
  const [validationError, setValidationError] = useState("")

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.push('/')
    }
  }, [isAuthenticated, router])

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
      setValidationError("请输入有效的邮箱地址")
      return
    }

    setSendingCode(true)
    setValidationError("")

    try {
      await sendVerificationCode({ email: email.trim() })
      setCodeSent(true)
      setCountdown(60)
    } catch (error) {
      // Error is already handled by the unified request layer
      console.error('Failed to send verification code:', error)
    } finally {
      setSendingCode(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError("")

    // Input validation
    if (!username.trim()) {
      setValidationError("请输入用户名")
      return
    }

    if (username.length < 2 || username.length > 50) {
      setValidationError("用户名长度应为 2-50 个字符")
      return
    }

    const usernameRegex = /^[a-zA-Z][a-zA-Z0-9_-]*$/
    if (!usernameRegex.test(username)) {
      setValidationError("用户名必须以字母开头,只能包含字母、数字、下划线和连字符")
      return
    }

    if (!email.trim()) {
      setValidationError("请输入邮箱")
      return
    }

    // Email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setValidationError("请输入有效的邮箱地址")
      return
    }

    if (!password) {
      setValidationError("请输入密码")
      return
    }

    if (password.length < 8) {
      setValidationError("密码长度至少为 8 个字符")
      return
    }

    // Password must contain both letters and numbers
    const hasLetter = /[a-zA-Z]/.test(password)
    const hasNumber = /\d/.test(password)
    if (!hasLetter || !hasNumber) {
      setValidationError("密码必须包含字母和数字")
      return
    }

    if (password !== confirmPassword) {
      setValidationError("两次输入的密码不一致")
      return
    }

    if (!verificationCode.trim()) {
      setValidationError("请输入验证码")
      return
    }

    if (verificationCode.length !== 6 || !/^\d{6}$/.test(verificationCode)) {
      setValidationError("验证码为 6 位数字")
      return
    }

    setIsLoading(true)

    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
        verification_code: verificationCode.trim(),
      })

      // Registration successful, redirect to home page
      router.push("/")
    } catch (error) {
      // Error is already handled by the unified request layer
      console.error('Registration failed:', error)
    } finally {
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
                placeholder="输入用户名 (字母开头,可含字母数字_-)"
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
                  验证码已发送至您的邮箱,请查收
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
                placeholder="输入密码 (至少 8 位,需含字母和数字)"
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

            {validationError && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                {validationError}
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
