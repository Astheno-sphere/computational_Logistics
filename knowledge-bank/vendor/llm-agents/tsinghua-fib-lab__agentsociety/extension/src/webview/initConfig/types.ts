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
  command: 'update' | 'initialData';
  text?: string;
  config?: InitConfig;
}

/**
 * Webview 发送到扩展的消息类型
 */
export interface WebviewMessage {
  command: 'save' | 'requestData';
  content?: string;
}

/**
 * 环境模块配置
 */
export interface EnvModuleConfig {
  module_type: string;
  kwargs: Record<string, any>;
}

/**
 * Agent 配置
 */
export interface AgentConfig {
  agent_id: number;
  agent_type: string;
  kwargs: AgentKwargs;
}

/**
 * Agent kwargs
 */
export interface AgentKwargs {
  id: number;
  name: string;
  [key: string]: any;
  profile?: Record<string, any>;
}

/**
 * init_config.json 完整结构
 */
export interface InitConfig {
  env_modules?: EnvModuleConfig[];
  agents?: AgentConfig[];
}
