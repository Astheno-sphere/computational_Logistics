/**
 * Types for the Environment & Agents webview.
 */

export interface VSCodeAPI {
  postMessage(message: Record<string, unknown>): void;
  getState(): unknown;
  setState(state: unknown): void;
}

export interface ClassInfo {
  type: string;
  class_name: string;
  description: string;
  init_description?: string;
  has_prefill?: boolean;
  is_custom?: boolean;
}

export interface AvailableClasses {
  success: boolean;
  env_modules: Record<string, ClassInfo>;
  agents: Record<string, ClassInfo>;
  env_module_count: number;
  agent_count: number;
}

export interface PrefillParams {
  version?: string;
  env_modules: Record<string, Record<string, unknown>>;
  agents: Record<string, Record<string, unknown>>;
}

export type ClassKind = 'env_module' | 'agent';
export type ListFilter = 'all' | 'prefill' | 'custom';
export type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export interface ClassItem {
  type: string;
  kind: ClassKind;
  info: ClassInfo;
  params: Record<string, unknown>;
}
