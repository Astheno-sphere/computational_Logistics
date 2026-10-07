/**
 * VSCode Webview API 类型定义
 */
export interface VSCodeAPI {
  postMessage(message: any): void;
  getState(): any;
  setState(state: any): void;
}

/**
 * 扩展发送到 Webview 的消息类型
 */
export interface ExtensionMessage {
  command: 'update' | 'loadData' | 'initialData';
  text?: string;
  settings?: SimSettings;
  agentClasses?: Record<string, AgentInfo>;
  envModules?: Record<string, EnvModuleInfo>;
}

/**
 * Webview 发送到扩展的消息类型
 */
export interface WebviewMessage {
  command: 'save' | 'requestData';
  content?: string;
}

/**
 * Agent 类信息
 */
export interface AgentInfo {
  type: string;
  class_name: string;
  description: string;
  is_custom?: boolean;
}

/**
 * Environment 模块类信息
 */
export interface EnvModuleInfo {
  type: string;
  class_name: string;
  description: string;
  is_custom?: boolean;
}

/**
 * SIM Settings 数据结构
 * 
 * 注意：hypothesis 和 groups 的详细信息已存储在 HYPOTHESIS.md 和 EXPERIMENT.md 中，
 * 这里只存储模拟配置相关的字段（agentClasses 和 envModules）。
 */
export interface SimSettings {
  /** Agent 类类型列表 */
  agentClasses?: string[];
  /** Environment 模块类型列表 */
  envModules?: string[];
}

