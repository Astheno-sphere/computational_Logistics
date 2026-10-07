export const ONBOARDING_KEYS = {
  hasCompletedInitialSetup: 'configPage.hasCompletedInitialSetup',
  configEntryTitleBarHintShown: 'projectStructure.configEntryTitleBarHintShown',
  firstSetupGuideShown: 'extension.firstSetupGuideShown',
  /** Last successful default-LLM connectivity check for this workspace. */
  defaultLlmValidation: 'configPage.defaultLlmValidation',
} as const;

export type DefaultLlmValidationCache = {
  fingerprint: string;
  at: number;
};
