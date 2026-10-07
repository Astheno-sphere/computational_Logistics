/**
 * Enums used in the application
 */

export enum LLMProviderType {
  OPENAI = 'openai',
  DEEPSEEK = 'deepseek',
  QWEN = 'qwen',
  ZHIPUAI = 'zhipuai',
  SILICONFLOW = 'siliconflow',
  VLLM = 'vllm'
}

export enum WorkflowType {
  STEP = "step",
  RUN = "run",
  INTERVIEW = "interview",
  SURVEY = "survey",
  ENVIRONMENT_INTERVENE = "environment",
  UPDATE_STATE_INTERVENE = "update_state",
  MESSAGE_INTERVENE = "message",
  NEXT_ROUND = "next_round",
  SAVE_CONTEXT = "save_context",
  // INTERVENE = "other",
  FUNCTION = "function"
}

export enum MetricType {
  FUNCTION = 'function',
  STATE = 'state'
}

export enum DistributionType {
  CHOICE = 'choice',
  UNIFORM_INT = 'uniform_int',
  UNIFORM_FLOAT = 'uniform_float',
  NORMAL = 'normal',
  CONSTANT = 'constant'
} 