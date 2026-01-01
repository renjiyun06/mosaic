/**
 * Unified HTTP request layer
 *
 * Key design principles:
 * - Always expects HTTP 200 (unless server crash)
 * - Checks response.success field instead of HTTP status
 * - Maps error.code to user-friendly Chinese messages
 */

import { API_BASE_URL, type ApiResponse } from './types'
import { getErrorMessage, getContextErrorMessage } from './error-messages'

// ==================== Types ====================

/**
 * Request options
 */
export interface RequestOptions extends Omit<RequestInit, 'body'> {
  auth?: boolean           // Whether to include auth token (default: true)
  body?: any               // Request body (will be JSON.stringify)
  context?: string         // Context key for context-specific error messages
  autoToast?: {
    success?: boolean | string  // Auto show success toast
    error?: boolean | string    // Auto show error toast
  }
}

// ==================== Custom Error Class ====================

/**
 * Custom API error class
 */
export class ApiError extends Error {
  constructor(
    public code: string,           // Error code from backend
    public message: string,        // User-friendly Chinese message
    public details?: any,          // Validation error details (optional)
    public backendMessage?: string // Original backend message (for debugging)
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /**
   * Check if error is a specific type
   */
  is(code: string): boolean {
    return this.code === code
  }

  /**
   * Check if error is authentication related
   */
  isAuthError(): boolean {
    return this.code === 'AUTHENTICATION_ERROR'
  }

  /**
   * Check if error is validation related
   */
  isValidationError(): boolean {
    return this.code === 'VALIDATION_ERROR'
  }
}

// ==================== Notification Helpers ====================

/**
 * Toast notification reference (will be set by NotificationProvider)
 */
let toastNotification: {
  success: (message: string) => void
  error: (message: string) => void
} | null = null

/**
 * Set toast notification functions (called by NotificationProvider)
 */
export function setToastNotification(notification: {
  success: (message: string) => void
  error: (message: string) => void
}) {
  toastNotification = notification
}

/**
 * Show toast notification
 */
function showToast(type: 'success' | 'error', message: string) {
  if (toastNotification) {
    toastNotification[type](message)
  } else {
    // Fallback to console if notification not initialized
    console.log(`[Toast ${type}]:`, message)
  }
}

// ==================== Auth Token Helpers ====================

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('auth_token')
}

/**
 * Clear auth token from localStorage
 */
function clearAuthToken(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem('auth_token')
}

// ==================== Error Handler ====================

/**
 * Handle API errors
 */
function handleApiError(error: ApiError, showToastOption: boolean | string = true) {
  // Special handling for authentication errors
  if (error.code === 'AUTHENTICATION_ERROR') {
    showToast('error', '登录已过期，请重新登录')
    clearAuthToken()
    // Redirect to login (next tick to avoid state update during render)
    setTimeout(() => {
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }, 0)
    return
  }

  // Auto show error toast
  if (showToastOption) {
    const message = typeof showToastOption === 'string'
      ? showToastOption
      : error.message
    showToast('error', message)
  }
}

// ==================== Main Request Function ====================

/**
 * Unified request function
 *
 * Key differences from traditional fetch:
 * - ALWAYS expects HTTP 200 (unless server crash)
 * - Checks response.success field instead of HTTP status
 * - Extracts error.code from response body
 * - Maps error codes to Chinese messages
 *
 * @example
 * // Basic usage
 * const data = await request<User>('/api/auth/me')
 *
 * // With context for better error messages
 * const mosaic = await request<Mosaic>('/api/mosaics/1/start', {
 *   method: 'POST',
 *   context: 'mosaic.start'
 * })
 *
 * // Custom auto-toast behavior
 * const user = await request<User>('/api/auth/login', {
 *   method: 'POST',
 *   body: { username, password },
 *   auth: false,
 *   autoToast: {
 *     success: '登录成功',
 *     error: true
 *   }
 * })
 */
export async function request<T>(
  url: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    auth = true,
    autoToast = { success: false, error: true },
    context,
    headers = {},
    body,
    ...fetchOptions
  } = options

  // 1. Build headers
  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string>)
  }

  // 2. Add auth token if needed
  if (auth) {
    const token = getAuthToken()
    if (token) {
      finalHeaders['Authorization'] = `Bearer ${token}`
    }
  }

  try {
    // 3. Make request
    const response = await fetch(API_BASE_URL + url, {
      ...fetchOptions,
      headers: finalHeaders,
      body: body ? JSON.stringify(body) : undefined
    })

    // 4. Check if response is JSON (backend should always return JSON)
    const contentType = response.headers.get('content-type')
    if (!contentType?.includes('application/json')) {
      throw new ApiError(
        'NETWORK_ERROR',
        '服务器返回了非 JSON 响应，可能发生了崩溃',
        { status: response.status }
      )
    }

    // 5. Parse JSON response
    const data: ApiResponse<T> = await response.json()

    // 6. Check success field (NOT HTTP status!)
    if (data.success) {
      // Success case
      if (autoToast.success) {
        const message = typeof autoToast.success === 'string'
          ? autoToast.success
          : data.message || '操作成功'
        showToast('success', message)
      }
      return data.data
    } else {
      // Business error case (still HTTP 200, but success=false)
      const errorCode = data.error?.code || 'UNKNOWN_ERROR'

      // Get user-friendly Chinese message from mapping table
      // IGNORE backend's message field - we control all user-facing text
      const userMessage = context
        ? getContextErrorMessage(context, errorCode, data.message)
        : getErrorMessage(errorCode, data.message)

      // Log unmapped errors in development
      if (process.env.NODE_ENV === 'development' && !getErrorMessage(errorCode)) {
        console.warn(
          `[Missing Error Mapping] Code: ${errorCode}, Backend message: ${data.message}`
        )
      }

      throw new ApiError(
        errorCode,
        userMessage,       // Use mapped Chinese message
        data.error?.details,
        data.message       // Store backend message for debugging
      )
    }

  } catch (error) {
    // 7. Handle exceptions

    // If already an ApiError, just handle and rethrow
    if (error instanceof ApiError) {
      handleApiError(error, autoToast.error)
      throw error
    }

    // Network error or fetch failure (server unreachable)
    if (error instanceof TypeError && error.message.includes('fetch')) {
      const networkError = new ApiError(
        'NETWORK_ERROR',
        '无法连接到服务器，请检查网络',
        null
      )
      handleApiError(networkError, autoToast.error)
      throw networkError
    }

    // Unknown error
    const unknownError = new ApiError(
      'UNKNOWN_ERROR',
      '发生未知错误',
      error
    )
    handleApiError(unknownError, autoToast.error)
    throw unknownError
  }
}
