import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as cp from 'child_process';
import type { ClaudeCodeCliStatus, ClaudeCodeConfigValues } from '../webview/configPage/claudeCodeTypes';
import { isLocalGatewayBaseUrl } from './aiCliGatewayUpstream';
export const CLAUDE_SETTINGS_DIR = path.join(os.homedir(), '.claude');
export const CLAUDE_SETTINGS_PATH = path.join(CLAUDE_SETTINGS_DIR, 'settings.json');

type EnvMappedKeys = Exclude<keyof ClaudeCodeConfigValues, 'permissionMode'>;
const ENV_KEY_MAP: Record<EnvMappedKeys, string> = {
  apiKey: 'ANTHROPIC_AUTH_TOKEN',
  baseUrl: 'ANTHROPIC_BASE_URL',
  model: 'ANTHROPIC_MODEL',
  sonnetModel: 'ANTHROPIC_DEFAULT_SONNET_MODEL',
  opusModel: 'ANTHROPIC_DEFAULT_OPUS_MODEL',
  fableModel: 'ANTHROPIC_DEFAULT_FABLE_MODEL',
  haikuModel: 'ANTHROPIC_DEFAULT_HAIKU_MODEL',
};

export function readClaudeSettingsFile(): Record<string, unknown> {
  try {
    if (!fs.existsSync(CLAUDE_SETTINGS_PATH)) {
      return {};
    }
    const raw = fs.readFileSync(CLAUDE_SETTINGS_PATH, 'utf-8');
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function readPermissionMode(settings: Record<string, unknown>): string {
  const topLevel = typeof settings.permissionMode === 'string' ? settings.permissionMode.trim() : '';
  if (topLevel) {
    return topLevel;
  }
  const permissions = settings.permissions as { defaultMode?: unknown } | undefined;
  return typeof permissions?.defaultMode === 'string' ? permissions.defaultMode.trim() : '';
}

export function extractClaudeConfig(settings: Record<string, unknown>): ClaudeCodeConfigValues {
  const env = (settings.env as Record<string, string> | undefined) ?? {};
  return {
    apiKey: (env[ENV_KEY_MAP.apiKey] ?? '').trim(),
    baseUrl: (env[ENV_KEY_MAP.baseUrl] ?? '').trim(),
    model: env[ENV_KEY_MAP.model] || '',
    sonnetModel: env[ENV_KEY_MAP.sonnetModel] || '',
    opusModel: env[ENV_KEY_MAP.opusModel] || '',
    fableModel: env[ENV_KEY_MAP.fableModel] || '',
    haikuModel: env[ENV_KEY_MAP.haikuModel] || '',
    permissionMode: readPermissionMode(settings),
  };
}

export function readClaudeConfig(): ClaudeCodeConfigValues {
  return extractClaudeConfig(readClaudeSettingsFile());
}

export function writeClaudeConfig(config: ClaudeCodeConfigValues): void {
  const existing = readClaudeSettingsFile();
  const env = { ...((existing.env as Record<string, string> | undefined) ?? {}) };

  const token = config.apiKey.trim();
  if (token) {
    env[ENV_KEY_MAP.apiKey] = token;
  } else {
    delete env[ENV_KEY_MAP.apiKey];
  }
  delete env.ANTHROPIC_API_KEY;
  const baseUrl = config.baseUrl.trim();
  if (baseUrl) {
    env[ENV_KEY_MAP.baseUrl] = baseUrl;
  } else {
    delete env[ENV_KEY_MAP.baseUrl];
  }

  (['model', 'sonnetModel', 'opusModel', 'fableModel', 'haikuModel'] as const).forEach((key) => {
    const val = (config[key] || '').trim();
    if (val) {
      env[ENV_KEY_MAP[key]] = val;
    } else {
      delete env[ENV_KEY_MAP[key]];
    }
  });

  if (!env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC) {
    env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1';
  }

  const updated: Record<string, unknown> = { ...existing, env };
  // Skip the WebFetch preflight request to the Anthropic server.
  if (updated.skipWebFetchPreflight !== true) {
    updated.skipWebFetchPreflight = true;
  }
  applyClaudePermissionAndEffortDefaults(updated, config.permissionMode);

  if (!fs.existsSync(CLAUDE_SETTINGS_DIR)) {
    fs.mkdirSync(CLAUDE_SETTINGS_DIR, { recursive: true });
  }

  const json = JSON.stringify(updated, null, 2);
  if (process.platform === 'win32') {
    fs.writeFileSync(CLAUDE_SETTINGS_PATH, json, 'utf-8');
  } else {
    const tmpPath = CLAUDE_SETTINGS_PATH + '.tmp';
    fs.writeFileSync(tmpPath, json, 'utf-8');
    try {
      fs.chmodSync(tmpPath, 0o600);
    } catch {
      /* ignore */
    }
    fs.renameSync(tmpPath, CLAUDE_SETTINGS_PATH);
  }
}

/**
 * Persist permission mode and high-intensity Claude Code defaults.
 *
 * Sets bypass-capable permission mode when requested, and always ensures
 * ``effortLevel=xhigh`` with workflows/ultracode enabled for AgentSociety-managed writes.
 */
function applyClaudePermissionAndEffortDefaults(
  settings: Record<string, unknown>,
  permissionMode?: string
): void {
  const mode = (permissionMode ?? '').trim() || 'bypassPermissions';
  settings.permissionMode = mode;
  const permissions =
    settings.permissions && typeof settings.permissions === 'object'
      ? { ...(settings.permissions as Record<string, unknown>) }
      : {};
  permissions.defaultMode = mode;
  settings.permissions = permissions;
  settings.effortLevel = 'xhigh';
  settings.enableWorkflows = true;
  settings.alwaysThinkingEnabled = true;
  settings.ultracode = true;
  if (settings.workflowKeywordTriggerEnabled !== false) {
    settings.workflowKeywordTriggerEnabled = true;
  }
}

export function isClaudeCodeEnvCustomized(): boolean {
  try {
    const env = (readClaudeSettingsFile().env as Record<string, string> | undefined) ?? {};
    if ((env[ENV_KEY_MAP.apiKey] ?? '').trim()) {
      return true;
    }
    const base = (env.ANTHROPIC_BASE_URL ?? '').trim();
    if (base) {
      return true;
    }
    return [
      'ANTHROPIC_MODEL',
      'ANTHROPIC_DEFAULT_SONNET_MODEL',
      'ANTHROPIC_DEFAULT_OPUS_MODEL',
      'ANTHROPIC_DEFAULT_FABLE_MODEL',
      'ANTHROPIC_DEFAULT_HAIKU_MODEL',
    ].some((key) => Boolean((env[key] ?? '').trim()));
  } catch {
    return false;
  }
}

/**
 * True when ~/.claude/settings.json points Claude Code at a non-AgentSociety endpoint.
 *
 * AgentSociety-managed routing uses either the local gateway (localhost base url) or a
 * direct upstream we wrote. We only flag user-authored configuration: an
 * ANTHROPIC_BASE_URL that is NOT a local gateway url is treated as user-owned. The
 * gateway-mode localhost base url is excluded so that our own prior writes do not
 * trigger a false positive.
 */
export function isClaudeCodeConfiguredByUser(): boolean {
  try {
    const env = (readClaudeSettingsFile().env as Record<string, string> | undefined) ?? {};
    const base = (env.ANTHROPIC_BASE_URL ?? '').trim();
    if (base && !isLocalGatewayBaseUrl(base)) {
      return true;
    }
    // An auth token set without any AgentSociety-managed base url is likely user-owned.
    if (!base && ((env.ANTHROPIC_AUTH_TOKEN ?? '').trim() || (env.ANTHROPIC_API_KEY ?? '').trim())) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export function applyClaudeOfficialSubscription(permissionMode?: string): void {
  const existing = readClaudeSettingsFile();
  const env = { ...((existing.env as Record<string, string> | undefined) ?? {}) };
  for (const key of [
    'ANTHROPIC_AUTH_TOKEN',
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_BASE_URL',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_DEFAULT_SONNET_MODEL',
    'ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_DEFAULT_FABLE_MODEL',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL',
  ]) {
    delete env[key];
  }
  if (!env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC) {
    env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1';
  }
  const updated: Record<string, unknown> = { ...existing, env };
  applyClaudePermissionAndEffortDefaults(updated, permissionMode);
  // Skip the WebFetch preflight request to the Anthropic server.
  if (updated.skipWebFetchPreflight !== true) {
    updated.skipWebFetchPreflight = true;
  }
  if (!fs.existsSync(CLAUDE_SETTINGS_DIR)) {
    fs.mkdirSync(CLAUDE_SETTINGS_DIR, { recursive: true });
  }
  const json = JSON.stringify(updated, null, 2);
  if (process.platform === 'win32') {
    fs.writeFileSync(CLAUDE_SETTINGS_PATH, json, 'utf-8');
    return;
  }
  const tmpPath = `${CLAUDE_SETTINGS_PATH}.tmp`;
  fs.writeFileSync(tmpPath, json, 'utf-8');
  try {
    fs.chmodSync(tmpPath, 0o600);
  } catch {
    /* ignore */
  }
  fs.renameSync(tmpPath, CLAUDE_SETTINGS_PATH);
}

export function detectClaudeCli(): Promise<ClaudeCodeCliStatus> {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => {
      resolve({ installed: false, error: '检测超时' });
    }, 5000);

    cp.execFile('claude', ['--version'], (error, stdout) => {
      clearTimeout(timeout);
      if (error) {
        resolve({ installed: false, error: 'Claude Code CLI 未安装' });
        return;
      }
      resolve({ installed: true, version: stdout.trim() });
    });
  });
}
