/**
 * API客户端 - 用于与FastAPI后端通信
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，创建ApiClient实例并传递给各组件
 * - @extension/src/prefillParamsViewProvider.ts - 使用ApiClient获取预填充参数
 * - @extension/src/projectStructureProvider.ts - 使用ApiClient进行项目初始化、模块扫描
 * - @extension/src/replayWebviewProvider.ts - 使用ApiClient获取回放数据（直接fetch，不通过此类）
 *
 * 后端API路由：
 * - @packages/agentsociety2/agentsociety2/backend/routers/prefill_params.py - /api/v1/prefill-params
 * - @packages/agentsociety2/agentsociety2/backend/routers/experiments.py - /api/v1/experiments
 * - @packages/agentsociety2/agentsociety2/backend/routers/replay.py - /api/v1/replay
 * - @packages/agentsociety2/agentsociety2/backend/routers/custom.py - /api/v1/custom
 * - @packages/agentsociety2/agentsociety2/backend/routers/modules.py - /api/v1/modules
 */

import * as vscode from 'vscode';
import { getBackendAccessUrl } from './runtimeConfig';
import { fetchCompat } from './shared/fetchCompat';
import { appendSharedOutputLine, OUTPUT_CHANNEL_MAIN } from './shared/outputChannels';

const fetch = fetchCompat as unknown as typeof globalThis.fetch;

/**
 * API客户端 - 用于与FastAPI后端通信
 */

/**
 * SSE事件类型
 */
export type SSEEventType = 'message' | 'tool' | 'complete' | 'heartbeat';

/**
 * SSE消息事件（MessageEvent）
 * 完全匹配后端 sse/models.py 中的 MessageEvent
 */
export interface MessageSSEEvent {
  type: 'message';
  content: string;
  is_thinking: boolean;
  is_error: boolean;
}

/**
 * SSE工具事件（ToolEvent）
 * 完全匹配后端 sse/models.py 中的 ToolEvent
 */
export interface ToolSSEEvent {
  type: 'tool';
  content: string;
  tool_name: string;
  tool_id: string;
  status: 'start' | 'progress' | 'success' | 'error';
}

/**
 * SSE完成事件（CompleteEvent）
 * 完全匹配后端 sse/models.py 中的 CompleteEvent
 */
export interface CompleteSSEEvent {
  type: 'complete';
  content: string;
}

/**
 * SSE心跳事件（HeartbeatEvent）
 * 完全匹配后端 sse/models.py 中的 HeartbeatEvent
 * 前端应该直接丢弃此事件，仅用于保持连接活跃
 */
export interface HeartbeatSSEEvent {
  type: 'heartbeat';
  content: string;
}

/**
 * SSE事件联合类型
 */
export type SSEEvent = MessageSSEEvent | ToolSSEEvent | CompleteSSEEvent | HeartbeatSSEEvent;

export interface MinerUParseRequest {
  file_path: string;
  workspace_path: string;
}

export interface MinerUParseResponse {
  success: boolean;
  message: string;
  parsed_file_path?: string;
  content_preview?: string;
}

export interface LiteratureDeleteRequest {
  file_path: string;
  workspace_path: string;
}

export interface LiteratureDeleteResponse {
  success: boolean;
  message: string;
}

export interface LiteratureRenameRequest {
  file_path: string;
  new_name: string;
  workspace_path: string;
}

export interface LiteratureRenameResponse {
  success: boolean;
  message: string;
  new_file_path?: string;
}

export interface AgentInfo {
  type: string;
  class_name: string;
  description: string;
  is_custom?: boolean;
}

export interface EnvModuleInfo {
  type: string;
  class_name: string;
  description: string;
  is_custom?: boolean;
}

export interface AgentsListResponse {
  success: boolean;
  agents: Record<string, AgentInfo>;
  count: number;
}

export interface EnvModulesListResponse {
  success: boolean;
  modules: Record<string, EnvModuleInfo>;
  count: number;
}

export interface WorkspaceInitRequest {
  workspace_path: string;
  topic: string;
}

export interface WorkspaceInitResponse {
  success: boolean;
  message: string;
  data?: {
    workspace_path: string;
    files_created: string[];
  };
}

export interface PrefillParams {
  version?: string;
  env_modules: Record<string, Record<string, any>>;
  agents: Record<string, Record<string, any>>;
}

export interface PrefillParamsResponse {
  success: boolean;
  data: PrefillParams;
}

export interface ClassPrefillParamsResponse {
  success: boolean;
  class_kind: string;
  class_name: string;
  params: Record<string, any>;
}

export interface ClassInfo {
  type: string;
  class_name: string;
  description: string;
  has_prefill?: boolean;
  is_custom?: boolean;
}

export interface AvailableClassesResponse {
  success: boolean;
  env_modules: Record<string, ClassInfo>;
  agents: Record<string, ClassInfo>;
  env_module_count: number;
  agent_count: number;
}

// ========== Custom Module API Interfaces ==========

export interface CustomModulesScanRequest {
  workspace_path?: string;
}

export interface CustomModulesTestRequest {
  workspace_path?: string;
  module_kind?: 'agent' | 'env_module';
  module_class_name?: string;
}

export interface CustomModulesScanResponse {
  success: boolean;
  agents_found: number;
  envs_found: number;
  agents_generated: number;
  envs_generated: number;
  errors: string[];
  message?: string;
}

export interface CustomModulesCleanResponse {
  success: boolean;
  removed_count: number;
  message: string;
}

export interface ModuleTestResult {
  name: string;
  success: boolean;
  output: string;
  error?: string;
}

export interface CustomModulesTestResponse {
  success: boolean;
  test_output: string;
  error?: string;
  returncode?: number;
  // 结构化测试结果
  results?: ModuleTestResult[];
  total_tests?: number;
  passed_tests?: number;
  failed_tests?: number;
}

export interface CustomModulesListResponse {
  success: boolean;
  agents: Array<{
    type: string;
    class_name: string;
    description: string;
    is_custom: boolean;
    module_path: string;
    file_path: string;
  }>;
  envs: Array<{
    type: string;
    class_name: string;
    description: string;
    is_custom: boolean;
    module_path: string;
    file_path: string;
  }>;
  total_agents: number;
  total_envs: number;
}

export interface CustomModulesStatusResponse {
  custom_dir_exists: boolean;
  agents_dir_exists: boolean;
  envs_dir_exists: boolean;
  agent_files_count: number;
  env_files_count: number;
  registered_agents: number;
  registered_envs: number;
}

// ── Agent Skills 接口 ──

export interface AgentSkillItem {
  skill_id: string;
  name: string;
  description: string;
  /** Registry source: `built-in` | `custom` | `env`. */
  source: string;
  source_label?: string;
  path: string;
  has_skill_md: boolean;
  script: string;
}

export interface AgentSkillsListResponse {
  success: boolean;
  skills: AgentSkillItem[];
  total: number;
}

export interface AgentSkillsSimpleResponse {
  success: boolean;
  message: string;
}

export interface AgentSkillsScanResponse {
  success: boolean;
  new_skills: string[];
  total: number;
  message: string;
}

export interface AgentSkillInfoResponse {
  success: boolean;
  skill_id: string;
  name: string;
  description: string;
  source: string;
  path: string;
  script: string;
  skill_md: string;
}

export class ApiClient {
  constructor(_context: vscode.ExtensionContext) {}

  /**
   * 获取后端URL（动态从.env文件读取）
   * 这样可以确保连接到实际运行的后端端口
   */
  private getBackendUrl(): string {
    try {
      return getBackendAccessUrl();
    } catch (error) {
      this.log(`Failed to read backend URL from .env: ${error}`);
    }
    // 后备方案：使用默认值
    return 'http://127.0.0.1:8001';
  }

  /**
   * 获取后端URL（公开方法）
   */
  getBaseUrl(): string {
    return this.getBackendUrl();
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    appendSharedOutputLine(OUTPUT_CHANNEL_MAIN, `[${timestamp}] [API] ${message}`);
  }

  /**
   * 处理fetch错误，提供更友好的错误消息
   */
  private handleFetchError(error: unknown, context: string): Error {
    const errorStr = String(error);

    // 检测连接错误
    if (
      errorStr.includes('ECONNREFUSED') ||
      errorStr.includes('fetch failed') ||
      errorStr.includes('NetworkError') ||
      errorStr.includes('Failed to fetch')
    ) {
      return new Error('后端服务未连接，请先启动后端服务');
    }

    // 检测超时
    if (errorStr.includes('timeout') || errorStr.includes('TimeoutError')) {
      return new Error('后端服务响应超时，请检查服务状态');
    }

    // 其他错误
    if (error instanceof Error) {
      return new Error(`${context}: ${error.message}`);
    }

    return new Error(`${context}: ${errorStr}`);
  }

  /**
   * 检查后端健康状态
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.getBackendUrl()}/health`);
      return response.ok;
    } catch (error) {
      this.log(`Health check failed: ${error}`);
      return false;
    }
  }

  /**
   * 使用MinerU解析文档
   */
  async parseWithMinerU(request: MinerUParseRequest): Promise<MinerUParseResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/mineru/parse`;
      this.log(`Sending MinerU parse request to ${url} for file: ${request.file_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`MinerU parse request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as MinerUParseResponse;
      this.log(`MinerU parse response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`MinerU parse request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 删除文献文件
   */
  async deleteLiterature(request: LiteratureDeleteRequest): Promise<LiteratureDeleteResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/literature/delete`;
      this.log(`Sending delete literature request to ${url} for file: ${request.file_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Delete literature request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as LiteratureDeleteResponse;
      this.log(`Delete literature response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Delete literature request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 重命名文献文件
   */
  async renameLiterature(request: LiteratureRenameRequest): Promise<LiteratureRenameResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/literature/rename`;
      this.log(`Sending rename literature request to ${url} for file: ${request.file_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Rename literature request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as LiteratureRenameResponse;
      this.log(`Rename literature response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Rename literature request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取所有可用的Agent类列表
   */
  async getAgentClasses(): Promise<AgentsListResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/modules/agent_classes`;
      this.log(`Fetching agent classes from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get agent classes request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as AgentsListResponse;
      this.log(`Agent classes fetched: ${data.count} agents available`);
      return data;
    } catch (error) {
      this.log(`Get agent classes request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取所有可用的Environment模块类列表
   */
  async getEnvModules(): Promise<EnvModulesListResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/modules/env_module_classes`;
      this.log(`Fetching env module classes from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get env modules request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as EnvModulesListResponse;
      this.log(`Env modules fetched: ${data.count} modules available`);
      return data;
    } catch (error) {
      this.log(`Get env modules request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 初始化工作区
   */
  async initWorkspace(request: WorkspaceInitRequest): Promise<WorkspaceInitResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/workspace/init`;
      this.log(`Sending workspace init request to ${url} for path: ${request.workspace_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Workspace init request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as WorkspaceInitResponse;
      this.log(`Workspace init response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Workspace init request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取全局预填充参数
   */
  async getPrefillParams(workspace_path: string): Promise<PrefillParamsResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/prefill-params?workspace_path=${encodeURIComponent(workspace_path)}`;
      this.log(`Fetching prefill params from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get prefill params request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as PrefillParamsResponse;
      this.log(`Prefill params fetched successfully`);
      return data;
    } catch (error) {
      this.log(`Get prefill params request failed: ${error}`);
      throw this.handleFetchError(error, '获取预填充参数失败');
    }
  }

  /**
   * 获取特定类的预填充参数
   */
  async getClassPrefillParams(
    workspace_path: string,
    class_kind: 'env_module' | 'agent',
    class_name: string
  ): Promise<ClassPrefillParamsResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/prefill-params/${class_kind}/${class_name}?workspace_path=${encodeURIComponent(workspace_path)}`;
      this.log(`Fetching class prefill params from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get class prefill params request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as ClassPrefillParamsResponse;
      this.log(`Class prefill params fetched successfully`);
      return data;
    } catch (error) {
      this.log(`Get class prefill params request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 列出所有可用的类（Agent和Env Module）
   */
  async getAvailableClasses(workspace_path: string): Promise<AvailableClassesResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/custom/classes?workspace_path=${encodeURIComponent(workspace_path)}`;
      this.log(`Fetching available classes from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get available classes request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as AvailableClassesResponse;
      this.log(`Available classes fetched: ${data.env_module_count} env modules, ${data.agent_count} agents`);
      return data;
    } catch (error) {
      this.log(`Get available classes request failed: ${error}`);
      throw this.handleFetchError(error, '获取类列表失败');
    }
  }

  // ========== Custom Module APIs ==========

  /**
   * 扫描自定义模块并生成 JSON 配置
   */
  async scanCustomModules(request: CustomModulesScanRequest): Promise<CustomModulesScanResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/custom/scan`;
      this.log(`Sending custom modules scan request to ${url}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Custom modules scan request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as CustomModulesScanResponse;
      this.log(`Custom modules scan response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Custom modules scan request failed: ${error}`);
      throw this.handleFetchError(error, '扫描模块失败');
    }
  }

  /**
   * 清理自定义模块配置
   */
  async cleanCustomModules(request: CustomModulesScanRequest): Promise<CustomModulesCleanResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/custom/clean`;
      this.log(`Sending custom modules clean request to ${url}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Custom modules clean request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as CustomModulesCleanResponse;
      this.log(`Custom modules clean response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Custom modules clean request failed: ${error}`);
      throw this.handleFetchError(error, '清理模块失败');
    }
  }

  /**
   * 测试自定义模块
   * @param.request 包含 workspace_path，可选的 module_kind 和 module_class_name
   * 如果指定 module_kind 和 module_class_name，则只测试指定模块
   */
  async testCustomModules(request: CustomModulesTestRequest): Promise<CustomModulesTestResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/custom/test`;
      this.log(`Sending custom modules test request to ${url}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Custom modules test request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as CustomModulesTestResponse;
      this.log(`Custom modules test response: success=${data.success}`);
      return data;
    } catch (error) {
      this.log(`Custom modules test request failed: ${error}`);
      throw this.handleFetchError(error, '测试模块失败');
    }
  }

  /**
   * 列出已注册的自定义模块
   */
  async listCustomModules(): Promise<CustomModulesListResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/custom/list`;
      this.log(`Fetching custom modules list from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get custom modules list request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as CustomModulesListResponse;
      this.log(`Custom modules list fetched: ${data.total_agents} agents, ${data.total_envs} envs`);
      return data;
    } catch (error) {
      this.log(`Get custom modules list request failed: ${error}`);
      throw this.handleFetchError(error, '获取模块列表失败');
    }
  }

  /**
   * 获取自定义模块状态
   */
  async getCustomModulesStatus(): Promise<CustomModulesStatusResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/custom/status`;
      this.log(`Fetching custom modules status from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get custom modules status request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as CustomModulesStatusResponse;
      this.log(`Custom modules status fetched`);
      return data;
    } catch (error) {
      this.log(`Get custom modules status request failed: ${error}`);
      throw this.handleFetchError(error, '获取模块状态失败');
    }
  }

  // ── Agent Skills API ──

  async listAgentSkills(): Promise<AgentSkillsListResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/agent-skills/list`;
      this.log(`Fetching agent skills from ${url}`);
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
      const data = await response.json() as AgentSkillsListResponse;
      this.log(`Agent skills fetched: ${data.total} skills`);
      return data;
    } catch (error) {
      this.log(`List agent skills failed: ${error}`);
      throw this.handleFetchError(error, '获取 Agent Skills 列表失败');
    }
  }

  async scanAgentSkills(workspace_path?: string): Promise<AgentSkillsScanResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/agent-skills/scan`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_path }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
      return await response.json() as AgentSkillsScanResponse;
    } catch (error) {
      this.log(`Scan agent skills failed: ${error}`);
      throw this.handleFetchError(error, '扫描 Agent Skills 失败');
    }
  }

  async importAgentSkill(source_path: string, workspace_path?: string): Promise<AgentSkillsSimpleResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/agent-skills/import`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_path, workspace_path }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
      return await response.json() as AgentSkillsSimpleResponse;
    } catch (error) {
      this.log(`Import agent skill failed: ${error}`);
      throw this.handleFetchError(error, '导入 Agent Skill 失败');
    }
  }

  async getAgentSkillInfo(skillId: string): Promise<AgentSkillInfoResponse> {
    try {
      const url = `${this.getBackendUrl()}/api/v1/agent-skills/${encodeURIComponent(skillId)}/info`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
      return await response.json() as AgentSkillInfoResponse;
    } catch (error) {
      this.log(`Get agent skill info failed: ${error}`);
      throw this.handleFetchError(error, '获取 Skill 信息失败');
    }
  }

}
