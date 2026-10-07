/**
 * AI Social Scientist - 统一消息协议
 *
 * 定义 Extension ↔ WebView 双向通信的所有消息类型
 */

// ============================================================================
// SSE 事件类型 (与后端对齐)
// ============================================================================

export type SSEEventType = 'message' | 'tool' | 'complete' | 'heartbeat';

export interface MessageSSEEvent {
  type: 'message';
  content: string;
  is_thinking: boolean;
  is_error: boolean;
}

export interface ToolSSEEvent {
  type: 'tool';
  content: string;
  tool_name: string;
  tool_id: string;
  status: 'start' | 'progress' | 'success' | 'error';
}

export interface CompleteSSEEvent {
  type: 'complete';
  content: string;
}

export interface HeartbeatSSEEvent {
  type: 'heartbeat';
  content: string;
}

export type SSEEvent =
  | MessageSSEEvent
  | ToolSSEEvent
  | CompleteSSEEvent
  | HeartbeatSSEEvent;

// ============================================================================
// 基础类型
// ============================================================================

export interface BackendStatus {
  connected: boolean;
  url?: string;
  error?: string;
}

// ============================================================================
// WebView → Extension 消息
// ============================================================================

/** 检查后端健康状态 */
export interface CheckHealthCommand {
  command: 'checkHealth';
}

/** 打开文件 */
export interface OpenFileCommand {
  command: 'openFile';
  filePath: string;
  line?: number;
}

/** 工具权限响应 */
export interface ToolPermissionResponseCommand {
  command: 'toolPermissionResponse';
  requestId: string;
  approved: boolean;
  remember?: boolean;
}

/** 中断当前对话 */
export interface InterruptCommand {
  command: 'interrupt';
}

/** WebView → Extension 所有消息类型 */
export type WebViewToExtensionMessage =
  | CheckHealthCommand
  | OpenFileCommand
  | ToolPermissionResponseCommand
  | InterruptCommand;

// ============================================================================
// Extension → WebView 消息
// ============================================================================

/** SSE 事件 */
export interface SSEEventMessage {
  command: 'sseEvent';
  event: SSEEvent;
}

/** 后端状态 */
export interface BackendStatusMessage {
  command: 'backendStatus';
  connected: boolean;
  url?: string;
}

/** 打开文件确认 */
export interface OpenFileMessage {
  command: 'openFile';
  filePath: string;
}

/** 工具权限请求 (新增) */
export interface ToolPermissionRequestMessage {
  command: 'toolPermissionRequest';
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  description: string;
  riskLevel: 'low' | 'medium' | 'high';
}

/** 实验状态更新 (新增) */
export interface ExperimentStatusMessage {
  command: 'experimentStatus';
  experimentId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  message?: string;
}

/** 流式对话已中断 */
export interface StreamInterruptedMessage {
  command: 'streamInterrupted';
}

/** Extension → WebView 所有消息类型 */
export type ExtensionToWebViewMessage =
  | SSEEventMessage
  | BackendStatusMessage
  | OpenFileMessage
  | ToolPermissionRequestMessage
  | ExperimentStatusMessage
  | StreamInterruptedMessage;
