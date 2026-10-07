/**
 * Codex 默认会带上 OpenAI 内置 `web_search` 工具；部分国产原生 /responses 网关
 * 的第一方模型不支持该工具，会直接返回 HTTP 400（"tool type 'web_search' is not supported"）。
 *
 * 黑名单来源：CC Switch v3.16.5（与其实测结论一致，采用「默认开启、仅禁用已知会拒收的」策略，
 * 避免误关 web_search 比误开更安全——误开必定 400）。
 *
 * 主机黑名单（第一方 API 域名）：
 * - xiaomimimo.com — 小米 MiMo（含 api.xiaomimimo.com、token-plan-cn.xiaomimimo.com 等子域）
 * - longcat.chat   — 美团 LongCat（含 api.longcat.chat）
 * - minimax.io / minimaxi.com — MiniMax 国内与国际站
 *
 * 模型轴前缀黑名单（剥掉聚合器 vendor/ 路径后匹配）：
 * - mimo / longcat / minimax — 对应品牌模型
 * - qwen3-coder — 仅压制百炼原生 coder 系（如 qwen3-coder-plus）；同主机通用 Qwen 不受影响
 */
const WEB_SEARCH_REJECT_HOSTS = [
  'xiaomimimo.com',
  'longcat.chat',
  'minimax.io',
  'minimaxi.com',
] as const;

const WEB_SEARCH_REJECT_MODEL_PREFIXES = [
  'mimo',
  'longcat',
  'minimax',
  'qwen3-coder',
] as const;

export const CODEX_WEB_SEARCH_DISABLED_VALUE = 'disabled';

function normalizeModelAxis(model: string): string {
  const trimmed = model.trim();
  const slash = trimmed.lastIndexOf('/');
  return slash >= 0 ? trimmed.slice(slash + 1) : trimmed;
}

export function shouldDisableCodexWebSearch(baseUrl: string, model?: string): boolean {
  let host = '';
  try {
    host = new URL(baseUrl.trim()).hostname.toLowerCase();
  } catch {
    host = baseUrl.trim().toLowerCase();
  }
  if (WEB_SEARCH_REJECT_HOSTS.some((rejectHost) => host === rejectHost || host.endsWith(`.${rejectHost}`))) {
    return true;
  }
  const axis = normalizeModelAxis(model ?? '').toLowerCase();
  if (!axis) {
    return false;
  }
  return WEB_SEARCH_REJECT_MODEL_PREFIXES.some(
    (prefix) => axis === prefix || axis.startsWith(`${prefix}-`) || axis.startsWith(`${prefix}_`)
  );
}
