/**
 * Type definitions for backend API
 *
 * Generated from:
 * - /home/tomato/zb/x/mosaic/src/mosaic/v2/backend/schema/*.py
 * - /home/tomato/zb/x/mosaic/src/mosaic/v2/backend/enum.py
 */

// ==================== API Response Types ====================

export interface SuccessResponse<T> {
  success: true
  message?: string
  data: T
}

export interface ErrorResponse {
  success: false
  message?: string
  data: null
  error?: {
    code: string
    details?: any
  }
}

export type ApiResponse<T> = SuccessResponse<T> | ErrorResponse

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ==================== Constants ====================

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://192.168.249.129:18888'

// ==================== Enums ====================

export enum NodeType {
  CLAUDE_CODE = 'claude_code',
  SCHEDULER = 'scheduler',
  EMAIL = 'email',
  AGGREGATOR = 'aggregator'
}

export enum MosaicStatus {
  STARTING = 'starting',
  RUNNING = 'running',
  STOPPED = 'stopped'
}

export enum NodeStatus {
  RUNNING = 'running',
  STOPPED = 'stopped'
}

export enum SessionAlignment {
  MIRRORING = 'mirroring',
  TASKING = 'tasking',
  AGENT_DRIVEN = 'agent_driven'
}

export enum EventType {
  SESSION_START = 'session_start',
  SESSION_RESPONSE = 'session_response',
  USER_PROMPT_SUBMIT = 'user_prompt_submit',
  PRE_TOOL_USE = 'pre_tool_use',
  POST_TOOL_USE = 'post_tool_use',
  SESSION_END = 'session_end',
  NODE_MESSAGE = 'node_message',
  EVENT_BATCH = 'event_batch',
  SYSTEM_MESSAGE = 'system_message',
  EMAIL_MESSAGE = 'email_message',
  SCHEDULER_MESSAGE = 'scheduler_message',
  REDDIT_SCRAPER_MESSAGE = 'reddit_scraper_message',
  USER_MESSAGE_EVENT = 'user_message_event'
}

export enum SessionStatus {
  ACTIVE = 'active',
  CLOSED = 'closed',
  ARCHIVED = 'archived'
}

export enum SessionMode {
  BACKGROUND = 'background',
  PROGRAM = 'program',
  CHAT = 'chat'
}

export enum LLMModel {
  SONNET = 'sonnet',
  OPUS = 'opus',
  HAIKU = 'haiku'
}

export enum MessageRole {
  SYSTEM = 'system',
  ASSISTANT = 'assistant',
  USER = 'user',
  NOTIFICATION = 'notification'
}

export enum MessageType {
  USER_MESSAGE = 'user_message',
  ASSISTANT_TEXT = 'assistant_text',
  ASSISTANT_THINKING = 'assistant_thinking',
  ASSISTANT_TOOL_USE = 'assistant_tool_use',
  ASSISTANT_TOOL_OUTPUT = 'assistant_tool_output',
  ASSISTANT_RESULT = 'assistant_result',
  SYSTEM_MESSAGE = 'system_message',
  SESSION_STARTED = 'session_started',
  SESSION_ENDED = 'session_ended',
  TOPIC_UPDATED = 'topic_updated'
}

// ==================== Auth Types ====================

export interface SendCodeRequest {
  email: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  verification_code: string
}

export interface LoginRequest {
  username_or_email: string
  password: string
}

export interface UserOut {
  id: number
  username: string
  email: string
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

export interface AuthResponse {
  user: UserOut
  access_token: string
  token_type: string
}

// ==================== Mosaic Types ====================

export interface CreateMosaicRequest {
  name: string
  description?: string | null
}

export interface UpdateMosaicRequest {
  name?: string | null
  description?: string | null
}

export interface MosaicOut {
  id: number
  user_id: number
  name: string
  description: string | null
  status: MosaicStatus
  node_count: number
  active_session_count: number
  created_at: string
  updated_at: string
}

// ==================== Topology Types ====================

export interface TopologyNodeOut {
  node_id: string
  node_type: string
  config: Record<string, any> | null
}

export interface TopologyConnectionOut {
  source_node_id: string
  target_node_id: string
  session_alignment: string
}

export interface TopologySubscriptionOut {
  source_node_id: string
  target_node_id: string
  event_type: string
}

export interface TopologyOut {
  nodes: TopologyNodeOut[]
  connections: TopologyConnectionOut[]
  subscriptions: TopologySubscriptionOut[]
}

// ==================== Node Types ====================

export interface CreateNodeRequest {
  node_id: string
  node_type: NodeType
  description?: string | null
  config?: Record<string, any> | null
  auto_start?: boolean
}

export interface UpdateNodeRequest {
  description?: string | null
  config?: Record<string, any> | null
  auto_start?: boolean | null
}

export interface NodeOut {
  id: number
  user_id: number
  mosaic_id: number
  node_id: string
  node_type: NodeType
  description: string | null
  config: Record<string, any>
  auto_start: boolean
  status: NodeStatus
  active_session_count: number
  created_at: string
  updated_at: string
}

// ==================== Workspace Types ====================

export interface WorkspaceStats {
  total_files: number
  total_directories: number
  total_size_bytes: number
}

export interface WorkspaceInfoOut {
  workspace_path: string
  node_id: string
  mosaic_id: number
  exists: boolean
  readable: boolean
  stats: WorkspaceStats | null
}

export interface WorkspaceFileItem {
  name: string
  path: string
  type: 'file' | 'directory'
  size: number | null
  modified_at: string
  extension: string | null
  mime_type: string | null
  children?: WorkspaceFileItem[]
}

export interface WorkspaceFilesOut {
  path: string
  absolute_path: string
  items: WorkspaceFileItem[]
}

export interface WorkspaceFileContentOut {
  path: string
  name: string
  size: number
  encoding: string
  content: string
  truncated: boolean
  mime_type: string | null
  language: string | null
}

// ==================== Connection Types ====================

export interface CreateConnectionRequest {
  source_node_id: string
  target_node_id: string
  session_alignment: SessionAlignment
  description?: string | null
}

export interface UpdateConnectionRequest {
  session_alignment?: SessionAlignment | null
  description?: string | null
}

export interface ConnectionOut {
  id: number
  user_id: number
  mosaic_id: number
  source_node_id: string
  target_node_id: string
  session_alignment: SessionAlignment
  description: string | null
  created_at: string
  updated_at: string
}

// ==================== Subscription Types ====================

export interface CreateSubscriptionRequest {
  connection_id: number
  event_type: EventType
  description?: string | null
}

export interface UpdateSubscriptionRequest {
  description?: string | null
}

export interface SubscriptionOut {
  id: number
  user_id: number
  mosaic_id: number
  connection_id: number
  source_node_id: string
  target_node_id: string
  event_type: EventType
  description: string | null
  created_at: string
  updated_at: string
}

// ==================== Session Types ====================

export interface CreateSessionRequest {
  mode: SessionMode
  model?: LLMModel | null
}

export interface ListSessionsRequest {
  session_id?: string | null
  status?: SessionStatus | null
  page?: number
  page_size?: number
}

export interface SessionOut {
  id: number
  session_id: string
  user_id: number
  mosaic_id: number
  node_id: string
  mode: SessionMode
  model: LLMModel | null
  status: SessionStatus
  topic: string | null
  message_count: number
  total_input_tokens: number
  total_output_tokens: number
  total_cost_usd: number
  created_at: string
  updated_at: string
  last_activity_at: string
  closed_at: string | null
  parent_session_id: string | null
  child_count: number
}

export interface SessionTopologyNode {
  session_id: string
  node_id: string
  status: SessionStatus
  parent_session_id: string | null
  children: SessionTopologyNode[]
  depth: number
  descendant_count: number
  created_at: string
  closed_at: string | null
}

export interface SessionTopologyResponse {
  root_session: SessionTopologyNode
  total_nodes: number
  max_depth: number
}

// ==================== Message Types ====================

export interface MessageOut {
  id: number
  message_id: string
  user_id: number
  mosaic_id: number
  node_id: string
  session_id: string
  role: MessageRole
  message_type: MessageType
  payload: any
  sequence: number
  created_at: string
}

// ==================== Event Types ====================

export interface EventListOut {
  event_id: string
  event_type: EventType
  source_node_id: string
  source_session_id: string
  target_node_id: string
  target_session_id: string
  created_at: string
}

export interface EventDetailOut {
  event_id: string
  event_type: EventType
  source_node_id: string
  source_session_id: string
  target_node_id: string
  target_session_id: string
  payload: any
  created_at: string
}

// ==================== SessionRouting Types ====================

export interface SessionRoutingOut {
  local_node_id: string
  local_session_id: string
  remote_node_id: string
  remote_session_id: string
  created_at: string
}

// ==================== Image Types ====================

export interface UploadImageResponse {
  image_id: string
  url: string
  thumbnail_url: string | null
  filename: string
  mime_type: string
  file_size: number
  width: number | null
  height: number | null
}

// ==================== CodeServer Types ====================

export type CodeServerStatus = 'starting' | 'running' | 'stopping' | 'stopped'

export interface CodeServerStatusOut {
  status: CodeServerStatus
  port: number | null
  url: string | null
  started_at: string | null
  ref_count: number | null
}

export interface CodeServerUrlOut {
  url: string
  workspace_path: string
}
