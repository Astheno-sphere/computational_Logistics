export interface ApiAgentTemplate {
  id: string;
  name: string;
  description: string;
  memory_distributions: Record<string, ApiDistributionConfig>;
  agent_params: Record<string, unknown>;
  blocks: Record<string, Record<string, unknown>>;
  created_at: string;
  updated_at: string;
  tenant_id?: string;
  agent_type?: string;
  agent_class?: string;
}

export enum ApiDistributionType {
  CHOICE = "choice",
  UNIFORM_INT = "uniform_int",
  NORMAL = "normal"
}

export interface ApiChoiceDistributionConfig {
  type: ApiDistributionType.CHOICE;
  choices: string[];
  weights: number[];
}

export interface ApiUniformIntDistributionConfig {
  type: ApiDistributionType.UNIFORM_INT;
  min_value: number;
  max_value: number;
}

export interface ApiNormalDistributionConfig {
  type: ApiDistributionType.NORMAL;
  mean: number;
  std: number;
}

export type ApiDistributionConfig = ApiChoiceDistributionConfig | ApiUniformIntDistributionConfig | ApiNormalDistributionConfig;

export interface ProfileField {
  label: string;
  type: 'discrete' | 'continuous';
  options?: string[];
  defaultParams?: {
    min_value?: number;
    max_value?: number;
    mean?: number;
    std?: number;
  };
}

export interface ApiNameTypeDescription {
  name: string;
  type: string;
  description: string | null;
  default?: unknown;
}

export interface ApiParam {
  name: string;
  type: 'bool' | 'int' | 'float' | 'str' | 'select' | 'select_multiple';
  description: string | null;
  default: unknown;
  required: boolean;
  options?: { label: string; value: string }[];
}

export interface ApiAgentParam {
  params_type: ApiParam[];
  context: ApiNameTypeDescription[];
  status_attributes: ApiNameTypeDescription[];
}

export interface ApiBlockParam {
  params_type: ApiParam[];
  context: ApiNameTypeDescription[];
}

export interface BlockContextInfo {
  blockName: string;
  context: ApiNameTypeDescription[];
}

export interface BlockInfo {
  block_name: string;
  description: string;
} 