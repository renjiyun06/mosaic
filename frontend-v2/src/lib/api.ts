/**
 * API Client for Mosaic backend
 *
 * All methods use the unified request function which:
 * - Automatically handles errors with Chinese messages
 * - Maps error codes to user-friendly messages
 * - Supports context-specific error messages
 * - Auto-shows toast notifications
 */

import { request } from './request'
import type {
  // Auth types
  SendCodeRequest,
  RegisterRequest,
  LoginRequest,
  UserOut,
  AuthResponse,

  // Mosaic types
  CreateMosaicRequest,
  UpdateMosaicRequest,
  MosaicOut,
  TopologyOut,

  // Node types
  CreateNodeRequest,
  UpdateNodeRequest,
  NodeOut,

  // Connection types
  CreateConnectionRequest,
  UpdateConnectionRequest,
  ConnectionOut,

  // Subscription types
  CreateSubscriptionRequest,
  UpdateSubscriptionRequest,
  SubscriptionOut,

  // Session types
  CreateSessionRequest,
  ListSessionsRequest,
  SessionOut,
  SessionTopologyResponse,

  // Message types
  MessageOut,

  // Event types
  EventListOut,
  EventDetailOut,

  // SessionRouting types
  SessionRoutingOut,

  // Workspace types
  WorkspaceInfoOut,
  WorkspaceFilesOut,
  WorkspaceFileContentOut,

  // CodeServer types
  CodeServerStatusOut,

  // Image types
  UploadImageResponse,

  // Utility types
  PaginatedData
} from './types'

// ==================== API Client Class ====================

class ApiClient {
  // ========================================================================
  // Authentication API
  // ========================================================================

  /**
   * Send verification code to email
   */
  async sendVerificationCode(data: SendCodeRequest): Promise<{ message: string }> {
    return request<{ message: string }>('/api/auth/send-code', {
      method: 'POST',
      body: data,
      auth: false,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Register new user account
   */
  async register(data: RegisterRequest): Promise<AuthResponse> {
    return request<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: data,
      auth: false,
      context: 'auth.register',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Login with username or email
   */
  async login(data: LoginRequest): Promise<AuthResponse> {
    return request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: data,
      auth: false,
      context: 'auth.login',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get current authenticated user info
   */
  async getCurrentUser(): Promise<UserOut> {
    return request<UserOut>('/api/auth/me', {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Logout current user
   */
  async logout(): Promise<void> {
    try {
      // Call backend logout endpoint
      await request<null>('/api/auth/logout', {
        method: 'POST',
        autoToast: {
          success: false,
          error: false
        }
      })
    } catch (error) {
      // Ignore logout errors - we'll clear token anyway
      console.error('Logout error:', error)
    } finally {
      // Always clear token from localStorage
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token')
      }
    }
  }

  // ========================================================================
  // Mosaic Management API
  // ========================================================================

  /**
   * Create a new mosaic instance
   */
  async createMosaic(data: CreateMosaicRequest): Promise<MosaicOut> {
    return request<MosaicOut>('/api/mosaics', {
      method: 'POST',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get all mosaic instances for current user
   */
  async listMosaics(): Promise<MosaicOut[]> {
    return request<MosaicOut[]>('/api/mosaics', {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get a single mosaic instance
   */
  async getMosaic(mosaicId: number): Promise<MosaicOut> {
    return request<MosaicOut>(`/api/mosaics/${mosaicId}`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Update a mosaic instance
   */
  async updateMosaic(mosaicId: number, data: UpdateMosaicRequest): Promise<MosaicOut> {
    return request<MosaicOut>(`/api/mosaics/${mosaicId}`, {
      method: 'PATCH',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Delete a mosaic instance
   */
  async deleteMosaic(mosaicId: number): Promise<null> {
    return request<null>(`/api/mosaics/${mosaicId}`, {
      method: 'DELETE',
      context: 'mosaic.delete',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Start a mosaic instance
   */
  async startMosaic(mosaicId: number): Promise<MosaicOut> {
    return request<MosaicOut>(`/api/mosaics/${mosaicId}/start`, {
      method: 'POST',
      context: 'mosaic.start',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Stop a mosaic instance
   */
  async stopMosaic(mosaicId: number): Promise<MosaicOut> {
    return request<MosaicOut>(`/api/mosaics/${mosaicId}/stop`, {
      method: 'POST',
      context: 'mosaic.stop',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get topology data for visualization
   */
  async getTopology(mosaicId: number): Promise<TopologyOut> {
    return request<TopologyOut>(`/api/mosaics/${mosaicId}/topology`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // Node Management API
  // ========================================================================

  /**
   * Create a new node in a mosaic
   */
  async createNode(mosaicId: number, data: CreateNodeRequest): Promise<NodeOut> {
    return request<NodeOut>(`/api/mosaics/${mosaicId}/nodes`, {
      method: 'POST',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get all nodes in a mosaic
   */
  async listNodes(mosaicId: number): Promise<NodeOut[]> {
    return request<NodeOut[]>(`/api/mosaics/${mosaicId}/nodes`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get a single node
   */
  async getNode(mosaicId: number, nodeId: string): Promise<NodeOut> {
    return request<NodeOut>(`/api/mosaics/${mosaicId}/nodes/${nodeId}`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Update a node
   */
  async updateNode(mosaicId: number, nodeId: string, data: UpdateNodeRequest): Promise<NodeOut> {
    return request<NodeOut>(`/api/mosaics/${mosaicId}/nodes/${nodeId}`, {
      method: 'PATCH',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Delete a node
   */
  async deleteNode(mosaicId: number, nodeId: string): Promise<null> {
    return request<null>(`/api/mosaics/${mosaicId}/nodes/${nodeId}`, {
      method: 'DELETE',
      context: 'node.delete',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Start a node
   */
  async startNode(mosaicId: number, nodeId: string): Promise<NodeOut> {
    return request<NodeOut>(`/api/mosaics/${mosaicId}/nodes/${nodeId}/start`, {
      method: 'POST',
      context: 'node.start',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Stop a node
   */
  async stopNode(mosaicId: number, nodeId: string): Promise<NodeOut> {
    return request<NodeOut>(`/api/mosaics/${mosaicId}/nodes/${nodeId}/stop`, {
      method: 'POST',
      context: 'node.stop',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get workspace information for a node
   */
  async getWorkspaceInfo(mosaicId: number, nodeId: string): Promise<WorkspaceInfoOut> {
    return request<WorkspaceInfoOut>(`/api/mosaics/${mosaicId}/nodes/${nodeId}/workspace`, {
      method: 'GET',
      context: 'node.workspace.info',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * List files in workspace
   */
  async listWorkspaceFiles(
    mosaicId: number,
    nodeId: string,
    params?: { path?: string; recursive?: boolean; max_depth?: number }
  ): Promise<WorkspaceFilesOut> {
    const queryParams = new URLSearchParams()
    if (params?.path) queryParams.append('path', params.path)
    if (params?.recursive !== undefined) queryParams.append('recursive', String(params.recursive))
    if (params?.max_depth !== undefined) queryParams.append('max_depth', String(params.max_depth))

    const queryString = queryParams.toString()
    const url = `/api/mosaics/${mosaicId}/nodes/${nodeId}/workspace/files${queryString ? '?' + queryString : ''}`

    return request<WorkspaceFilesOut>(url, {
      method: 'GET',
      context: 'node.workspace.files',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get file content from workspace
   */
  async getWorkspaceFileContent(
    mosaicId: number,
    nodeId: string,
    params: { path: string; encoding?: string; max_size?: number }
  ): Promise<WorkspaceFileContentOut> {
    const queryParams = new URLSearchParams()
    queryParams.append('path', params.path)
    if (params.encoding) queryParams.append('encoding', params.encoding)
    if (params.max_size !== undefined) queryParams.append('max_size', String(params.max_size))

    return request<WorkspaceFileContentOut>(
      `/api/mosaics/${mosaicId}/nodes/${nodeId}/workspace/file-content?${queryParams}`,
      {
        method: 'GET',
        context: 'node.workspace.content',
        autoToast: {
          success: false,
          error: true
        }
      }
    )
  }

  // ========================================================================
  // Code-Server API
  // ========================================================================

  /**
   * Start code-server instance for a node
   */
  async startCodeServer(mosaicId: number, nodeId: string): Promise<CodeServerStatusOut> {
    return request<CodeServerStatusOut>(
      `/api/mosaics/${mosaicId}/nodes/${nodeId}/code-server/start`,
      {
        method: 'POST',
        context: 'node.codeserver.start',
        autoToast: {
          success: false,
          error: true
        }
      }
    )
  }

  /**
   * Stop code-server instance for a node (release reference)
   */
  async stopCodeServer(mosaicId: number, nodeId: string): Promise<null> {
    return request<null>(
      `/api/mosaics/${mosaicId}/nodes/${nodeId}/code-server/stop`,
      {
        method: 'POST',
        context: 'node.codeserver.stop',
        autoToast: {
          success: false,
          error: true
        }
      }
    )
  }

  /**
   * Force stop code-server instance for a node (ignore ref_count)
   */
  async forceStopCodeServer(mosaicId: number, nodeId: string): Promise<null> {
    return request<null>(
      `/api/mosaics/${mosaicId}/nodes/${nodeId}/code-server/force-stop`,
      {
        method: 'POST',
        context: 'node.codeserver.forcestop',
        autoToast: {
          success: false,
          error: true
        }
      }
    )
  }

  /**
   * Get code-server instance status for a node
   */
  async getCodeServerStatus(mosaicId: number, nodeId: string): Promise<CodeServerStatusOut> {
    return request<CodeServerStatusOut>(
      `/api/mosaics/${mosaicId}/nodes/${nodeId}/code-server/status`,
      {
        method: 'GET',
        context: 'node.codeserver.status',
        autoToast: {
          success: false,
          error: true
        }
      }
    )
  }

  // ========================================================================
  // Connection Management API
  // ========================================================================

  /**
   * Create a connection between nodes
   */
  async createConnection(mosaicId: number, data: CreateConnectionRequest): Promise<ConnectionOut> {
    return request<ConnectionOut>(`/api/mosaics/${mosaicId}/connections`, {
      method: 'POST',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get all connections in a mosaic
   */
  async listConnections(mosaicId: number): Promise<ConnectionOut[]> {
    return request<ConnectionOut[]>(`/api/mosaics/${mosaicId}/connections`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get a single connection
   */
  async getConnection(mosaicId: number, connectionId: number): Promise<ConnectionOut> {
    return request<ConnectionOut>(`/api/mosaics/${mosaicId}/connections/${connectionId}`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Update a connection
   */
  async updateConnection(
    mosaicId: number,
    connectionId: number,
    data: UpdateConnectionRequest
  ): Promise<ConnectionOut> {
    return request<ConnectionOut>(`/api/mosaics/${mosaicId}/connections/${connectionId}`, {
      method: 'PATCH',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Delete a connection
   */
  async deleteConnection(mosaicId: number, connectionId: number): Promise<null> {
    return request<null>(`/api/mosaics/${mosaicId}/connections/${connectionId}`, {
      method: 'DELETE',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // Subscription Management API
  // ========================================================================

  /**
   * Create a subscription on a connection
   */
  async createSubscription(mosaicId: number, data: CreateSubscriptionRequest): Promise<SubscriptionOut> {
    return request<SubscriptionOut>(`/api/mosaics/${mosaicId}/subscriptions`, {
      method: 'POST',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get all subscriptions in a mosaic
   */
  async listSubscriptions(mosaicId: number): Promise<SubscriptionOut[]> {
    return request<SubscriptionOut[]>(`/api/mosaics/${mosaicId}/subscriptions`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get a single subscription
   */
  async getSubscription(mosaicId: number, subscriptionId: number): Promise<SubscriptionOut> {
    return request<SubscriptionOut>(`/api/mosaics/${mosaicId}/subscriptions/${subscriptionId}`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Update a subscription
   */
  async updateSubscription(
    mosaicId: number,
    subscriptionId: number,
    data: UpdateSubscriptionRequest
  ): Promise<SubscriptionOut> {
    return request<SubscriptionOut>(`/api/mosaics/${mosaicId}/subscriptions/${subscriptionId}`, {
      method: 'PATCH',
      body: data,
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Delete a subscription
   */
  async deleteSubscription(mosaicId: number, subscriptionId: number): Promise<null> {
    return request<null>(`/api/mosaics/${mosaicId}/subscriptions/${subscriptionId}`, {
      method: 'DELETE',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // Session Management API
  // ========================================================================

  /**
   * Create a new session for a node
   */
  async createSession(mosaicId: number, nodeId: string, data: CreateSessionRequest): Promise<SessionOut> {
    return request<SessionOut>(`/api/mosaics/${mosaicId}/sessions`, {
      method: 'POST',
      body: {
        node_id: nodeId,
        ...data
      },
      context: 'session.create',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Close a session
   */
  async closeSession(mosaicId: number, nodeId: string, sessionId: string): Promise<SessionOut> {
    return request<SessionOut>(`/api/mosaics/${mosaicId}/sessions/${sessionId}/close`, {
      method: 'POST',
      context: 'session.close',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Archive a session
   */
  async archiveSession(mosaicId: number, nodeId: string, sessionId: string): Promise<SessionOut> {
    return request<SessionOut>(`/api/mosaics/${mosaicId}/sessions/${sessionId}/archive`, {
      method: 'POST',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Batch archive all closed sessions
   */
  async batchArchiveSessions(mosaicId: number, nodeId?: string): Promise<{ archived_count: number; failed_sessions: string[] }> {
    const queryParams = new URLSearchParams()
    if (nodeId) queryParams.append('node_id', nodeId)

    const url = `/api/mosaics/${mosaicId}/sessions/batch-archive${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return request<{ archived_count: number; failed_sessions: string[] }>(url, {
      method: 'POST',
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * List sessions with filters and pagination
   */
  async listSessions(mosaicId: number, nodeId?: string, params?: ListSessionsRequest): Promise<PaginatedData<SessionOut>> {
    const queryParams = new URLSearchParams()

    if (nodeId) queryParams.append('node_id', nodeId)
    if (params?.session_id) queryParams.append('session_id', params.session_id)
    if (params?.status) queryParams.append('status', params.status)
    if (params?.page) queryParams.append('page', params.page.toString())
    if (params?.page_size) queryParams.append('page_size', params.page_size.toString())

    const queryString = queryParams.toString()
    const url = `/api/mosaics/${mosaicId}/sessions${queryString ? `?${queryString}` : ''}`

    return request<PaginatedData<SessionOut>>(url, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  /**
   * Get session topology tree starting from a root session
   */
  async getSessionTopology(
    mosaicId: number,
    sessionId: string,
    maxDepth?: number
  ): Promise<SessionTopologyResponse> {
    const queryParams = new URLSearchParams()

    if (maxDepth !== undefined) {
      queryParams.append('max_depth', maxDepth.toString())
    }

    const queryString = queryParams.toString()
    const url = `/api/mosaics/${mosaicId}/sessions/${sessionId}/topology${queryString ? `?${queryString}` : ''}`

    return request<SessionTopologyResponse>(url, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // Message API
  // ========================================================================

  /**
   * List messages in a mosaic with optional filters and pagination
   */
  async listMessages(
    mosaicId: number,
    options?: {
      nodeId?: string
      sessionId?: string
      page?: number
      pageSize?: number
    }
  ): Promise<PaginatedData<MessageOut>> {
    const queryParams = new URLSearchParams()

    if (options?.nodeId) queryParams.append('node_id', options.nodeId)
    if (options?.sessionId) queryParams.append('session_id', options.sessionId)
    if (options?.page) queryParams.append('page', options.page.toString())
    if (options?.pageSize) queryParams.append('page_size', options.pageSize.toString())

    const queryString = queryParams.toString()
    const url = `/api/mosaics/${mosaicId}/messages${queryString ? `?${queryString}` : ''}`

    return request<PaginatedData<MessageOut>>(url, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // Event API
  // ========================================================================

  /**
   * List events in a mosaic with filters and pagination
   */
  async listEvents(
    mosaicId: number,
    params: {
      created_at_start: string  // ISO datetime string (required)
      created_at_end: string    // ISO datetime string (required)
      source_node_id?: string
      source_session_id?: string
      target_node_id?: string
      target_session_id?: string
      event_type?: string
      page?: number
      page_size?: number
    }
  ): Promise<PaginatedData<EventListOut>> {
    const queryParams = new URLSearchParams()

    // Required parameters
    queryParams.append('created_at_start', params.created_at_start)
    queryParams.append('created_at_end', params.created_at_end)

    // Optional parameters
    if (params.source_node_id) queryParams.append('source_node_id', params.source_node_id)
    if (params.source_session_id) queryParams.append('source_session_id', params.source_session_id)
    if (params.target_node_id) queryParams.append('target_node_id', params.target_node_id)
    if (params.target_session_id) queryParams.append('target_session_id', params.target_session_id)
    if (params.event_type) queryParams.append('event_type', params.event_type)

    // Pagination parameters
    queryParams.append('page', String(params.page || 1))
    queryParams.append('page_size', String(params.page_size || 100))

    return request<PaginatedData<EventListOut>>(
      `/api/mosaics/${mosaicId}/events?${queryParams.toString()}`,
      {
        autoToast: {
          success: false,
          error: true
        }
      }
    )
  }

  /**
   * Get detailed event information
   */
  async getEvent(mosaicId: number, eventId: string): Promise<EventDetailOut> {
    return request<EventDetailOut>(`/api/mosaics/${mosaicId}/events/${eventId}`, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // SessionRouting API
  // ========================================================================

  /**
   * List session routing mappings with filters and pagination
   */
  async listSessionRoutings(
    mosaicId: number,
    options?: {
      localNodeId?: string
      localSessionId?: string
      remoteNodeId?: string
      remoteSessionId?: string
      page?: number
      pageSize?: number
    }
  ): Promise<PaginatedData<SessionRoutingOut>> {
    const queryParams = new URLSearchParams()

    if (options?.localNodeId) queryParams.append('local_node_id', options.localNodeId)
    if (options?.localSessionId) queryParams.append('local_session_id', options.localSessionId)
    if (options?.remoteNodeId) queryParams.append('remote_node_id', options.remoteNodeId)
    if (options?.remoteSessionId) queryParams.append('remote_session_id', options.remoteSessionId)
    if (options?.page) queryParams.append('page', options.page.toString())
    if (options?.pageSize) queryParams.append('page_size', options.pageSize.toString())

    const queryString = queryParams.toString()
    const url = `/api/mosaics/${mosaicId}/session-routings${queryString ? `?${queryString}` : ''}`

    return request<PaginatedData<SessionRoutingOut>>(url, {
      autoToast: {
        success: false,
        error: true
      }
    })
  }

  // ========================================================================
  // Image API
  // ========================================================================

  /**
   * Upload image file
   * Returns full URLs for original image and thumbnail
   */
  async uploadImage(file: File): Promise<UploadImageResponse> {
    const formData = new FormData()
    formData.append('file', file)

    return request<UploadImageResponse>('/api/images/upload', {
      method: 'POST',
      body: formData,
      isFormData: true,
      autoToast: {
        success: false,
        error: true
      }
    })
  }
}

// Global API client instance
export const apiClient = new ApiClient()

// Re-export ApiError for use in components
export { ApiError } from './request'
