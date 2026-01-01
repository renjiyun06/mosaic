/**
 * Error code to Chinese message mapping
 *
 * This file maintains all error messages shown to users.
 * Backend's message field is ignored - we control all user-facing text.
 */

export const ERROR_MESSAGES: Record<string, string> = {
  // ==================== Basic Business Errors (6) ====================

  'VALIDATION_ERROR': '输入信息有误，请检查后重试',
  'CONFLICT': '该资源已存在，请使用其他名称',
  'AUTHENTICATION_ERROR': '用户名或密码错误',
  'NOT_FOUND': '请求的资源不存在',
  'PERMISSION_DENIED': '您没有权限执行此操作',
  'INTERNAL_ERROR': '系统内部错误，请稍后重试',

  // ==================== Runtime Configuration Errors (3) ====================

  'RUNTIME_CONFIG_ERROR': '运行时配置错误',
  'RUNTIME_ALREADY_STARTED': '运行时管理器已启动',
  'RUNTIME_NOT_STARTED': '运行时管理器未启动',

  // ==================== Mosaic State Errors (3) ====================

  'MOSAIC_ALREADY_RUNNING': '该 Mosaic 已经在运行中',
  'MOSAIC_STARTING': '该 Mosaic 正在启动，请稍候',
  'MOSAIC_NOT_RUNNING': '该 Mosaic 未运行',

  // ==================== Node State Errors (3) ====================

  'NODE_ALREADY_RUNNING': '该节点已经在运行中',
  'NODE_NOT_RUNNING': '该节点未运行',
  'NODE_NOT_FOUND': '该节点不存在',

  // ==================== Session Errors (2) ====================

  'SESSION_NOT_FOUND': '会话不存在或已关闭',
  'SESSION_CONFLICT': '会话 ID 冲突，请重试',

  // ==================== Timeout & Internal Errors (2) ====================

  'RUNTIME_TIMEOUT': '操作超时，请检查系统状态后重试',
  'RUNTIME_INTERNAL_ERROR': '运行时内部错误',

  // ==================== Frontend Network Errors (2) ====================

  'NETWORK_ERROR': '网络连接失败，请检查网络后重试',
  'UNKNOWN_ERROR': '发生未知错误，请稍后重试'
}

/**
 * Get user-friendly error message by error code
 */
export function getErrorMessage(code: string, fallbackMessage?: string): string {
  return ERROR_MESSAGES[code] || fallbackMessage || ERROR_MESSAGES['UNKNOWN_ERROR']
}

/**
 * Context-specific error messages (optional - for special cases)
 *
 * Some errors need different messages in different contexts.
 * Example: "MOSAIC_ALREADY_RUNNING" when starting vs. when creating
 */
export const CONTEXT_ERROR_MESSAGES: Record<string, Record<string, string>> = {
  // ==================== Authentication Context ====================

  'auth.login': {
    'AUTHENTICATION_ERROR': '用户名或密码错误，请重试',
    'VALIDATION_ERROR': '请输入正确的用户名和密码'
  },

  'auth.register': {
    'CONFLICT': '该用户名或邮箱已被注册',
    'VALIDATION_ERROR': '请检查输入信息格式'
  },

  // ==================== Mosaic Operations Context ====================

  'mosaic.start': {
    'MOSAIC_ALREADY_RUNNING': '该 Mosaic 已在运行中，无需重复启动',
    'MOSAIC_STARTING': '该 Mosaic 正在启动中，请稍候',
    'RUNTIME_TIMEOUT': 'Mosaic 启动超时，请检查配置后重试'
  },

  'mosaic.stop': {
    'MOSAIC_NOT_RUNNING': '该 Mosaic 未运行，无需停止',
    'RUNTIME_TIMEOUT': 'Mosaic 停止超时，请稍后重试'
  },

  'mosaic.delete': {
    'PERMISSION_DENIED': '无法删除运行中的 Mosaic，请先停止后再删除',
    'NOT_FOUND': '该 Mosaic 不存在或已被删除'
  },

  // ==================== Node Operations Context ====================

  'node.start': {
    'NODE_ALREADY_RUNNING': '该节点已在运行中',
    'MOSAIC_NOT_RUNNING': '请先启动 Mosaic 后再启动节点',
    'RUNTIME_TIMEOUT': '节点启动超时，请检查配置'
  },

  'node.stop': {
    'NODE_NOT_RUNNING': '该节点未运行',
    'RUNTIME_TIMEOUT': '节点停止超时'
  },

  'node.delete': {
    'PERMISSION_DENIED': '无法删除运行中的节点，请先停止',
    'NODE_NOT_FOUND': '该节点不存在或已被删除'
  },

  // ==================== Session Operations Context ====================

  'session.create': {
    'MOSAIC_NOT_RUNNING': '请先启动 Mosaic 后再创建会话',
    'NODE_NOT_RUNNING': '请先启动节点后再创建会话',
    'SESSION_CONFLICT': '会话创建冲突，请稍后重试'
  },

  'session.close': {
    'SESSION_NOT_FOUND': '该会话不存在或已关闭'
  }
}

/**
 * Get context-specific error message
 */
export function getContextErrorMessage(
  context: string,
  code: string,
  fallbackMessage?: string
): string {
  return CONTEXT_ERROR_MESSAGES[context]?.[code]
    || ERROR_MESSAGES[code]
    || fallbackMessage
    || ERROR_MESSAGES['UNKNOWN_ERROR']
}
