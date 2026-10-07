/**
 * Request shape fixes for Anthropic-compatible traffic (aligned with cc-switch).
 *
 * PRE-SEND: heuristic text-only image strip.
 * POST-ERROR: thinking signature / budget / unsupported-image, each at most once.
 */

export type GatewayRectifierSettings = {
  enabled: boolean;
  thinkingSignature: boolean;
  thinkingBudget: boolean;
  unsupportedImageDowngrade: boolean;
  heuristicTextOnlyModels: boolean;
};

export const DEFAULT_GATEWAY_RECTIFIER_SETTINGS: GatewayRectifierSettings = {
  enabled: true,
  thinkingSignature: true,
  thinkingBudget: true,
  unsupportedImageDowngrade: true,
  heuristicTextOnlyModels: true,
};

export const UNSUPPORTED_IMAGE_MARKER = '[Unsupported Image]';

const MAX_THINKING_BUDGET = 32_000;
const MAX_TOKENS_VALUE = 64_000;
const MIN_MAX_TOKENS_FOR_BUDGET = MAX_THINKING_BUDGET + 1;

/** Exact tails only (cc-switch `is_confirmed_text_only_model`). Fail-open for unknowns. */
const CONFIRMED_TEXT_ONLY_TAILS = new Set([
  'ark-code-latest',
  'deepseek-chat',
  'deepseek-reasoner',
  'deepseek-v4-flash',
  'deepseek-v4-pro',
  'glm-5.1',
  'glm-5.2',
  'kat-coder',
  'kat-coder-pro',
  'kat-coder-pro v1',
  'kat-coder-pro v2',
  'kat-coder-pro-v1',
  'kat-coder-pro-v2',
  'ling-2.5-1t',
  'longcat-2.0',
  'longcat-flash-chat',
  'minimax-m2.7',
  'minimax-m2.7-highspeed',
  'mimo-v2.5-pro',
  'qwen3-coder-480b',
  'qwen3-coder-480b-a35b-instruct',
  'qwen3-coder-flash',
  'qwen3-coder-next',
  'qwen3-coder-plus',
  'step-3.5-flash',
  'step-3.5-flash-2603',
  'us.deepseek.r1-v1',
]);

const ONE_M_CONTEXT_MARKER = '[1m]';

const IMAGE_BLOCK_TYPES = new Set([
  'image',
  'image_url',
  'input_image',
  'image_url_url',
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeModelIdForTextOnly(model: string): string {
  let normalized = model.trim().replace(/^models\//i, '').trim().toLowerCase();
  if (normalized.endsWith(ONE_M_CONTEXT_MARKER)) {
    normalized = normalized.slice(0, -ONE_M_CONTEXT_MARKER.length).trim();
  }
  return normalized;
}

export function isLikelyTextOnlyModel(model: string): boolean {
  const normalized = normalizeModelIdForTextOnly(model);
  if (!normalized) {
    return false;
  }
  const slash = normalized.lastIndexOf('/');
  const tail = slash >= 0 ? normalized.slice(slash + 1) : normalized;
  return CONFIRMED_TEXT_ONLY_TAILS.has(tail);
}

function isImageBlockType(type: unknown): boolean {
  return typeof type === 'string' && IMAGE_BLOCK_TYPES.has(type);
}

function contentHasImageBlocks(content: unknown): boolean {
  if (!Array.isArray(content)) {
    return false;
  }
  return content.some((block) => {
    if (!isObject(block)) {
      return false;
    }
    if (isImageBlockType(block.type)) {
      return true;
    }
    return contentHasImageBlocks(block.content);
  });
}

export function containsImageBlocks(body: Record<string, unknown>): boolean {
  if (Array.isArray(body.messages)) {
    for (const message of body.messages) {
      if (isObject(message) && contentHasImageBlocks(message.content)) {
        return true;
      }
    }
  }
  if (body.input !== undefined && responsesInputHasImages(body.input)) {
    return true;
  }
  return false;
}

function responsesInputHasImages(input: unknown): boolean {
  if (Array.isArray(input)) {
    return input.some((item) => responsesInputItemHasImages(item));
  }
  if (isObject(input)) {
    return responsesInputItemHasImages(input);
  }
  return false;
}

function responsesInputItemHasImages(item: unknown): boolean {
  if (!isObject(item)) {
    return false;
  }
  if (item.type === 'input_image' || isImageBlockType(item.type)) {
    return true;
  }
  return contentHasImageBlocks(item.content);
}

function replaceImagesInContent(content: unknown, textType = 'text'): { content: unknown; replaced: number } {
  if (!Array.isArray(content)) {
    return { content, replaced: 0 };
  }
  let replaced = 0;
  const next = content.map((block) => {
    if (!isObject(block)) {
      return block;
    }
    if (isImageBlockType(block.type)) {
      replaced += 1;
      return { type: textType, text: UNSUPPORTED_IMAGE_MARKER };
    }
    if (block.content !== undefined) {
      const nested = replaceImagesInContent(block.content, textType);
      replaced += nested.replaced;
      return { ...block, content: nested.content };
    }
    return block;
  });
  return { content: next, replaced };
}

function replaceImagesInResponsesInput(input: unknown): { input: unknown; replaced: number } {
  if (Array.isArray(input)) {
    let replaced = 0;
    const next = input.map((item) => {
      const result = replaceResponsesInputItem(item);
      replaced += result.replaced;
      return result.item;
    });
    return { input: next, replaced };
  }
  if (isObject(input)) {
    const replaced = replaceResponsesInputItem(input);
    return { input: replaced.item, replaced: replaced.replaced };
  }
  return { input, replaced: 0 };
}

function replaceResponsesInputItem(item: unknown): { item: unknown; replaced: number } {
  if (!isObject(item)) {
    return { item, replaced: 0 };
  }
  if (item.type === 'input_image' || isImageBlockType(item.type)) {
    return {
      item: { type: 'input_text', text: UNSUPPORTED_IMAGE_MARKER },
      replaced: 1,
    };
  }
  if (item.content !== undefined) {
    const nested = replaceImagesInContent(item.content, 'input_text');
    return { item: { ...item, content: nested.content }, replaced: nested.replaced };
  }
  return { item, replaced: 0 };
}

export function downgradeUnsupportedImages(body: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...body };
  if (Array.isArray(next.messages)) {
    next.messages = next.messages.map((message) => {
      if (!isObject(message)) {
        return message;
      }
      const { content } = replaceImagesInContent(message.content);
      return { ...message, content };
    });
  }
  if (next.input !== undefined) {
    next.input = replaceImagesInResponsesInput(next.input).input;
  }
  return next;
}

export function stripIncompatibleThinking(body: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...body };

  if (Array.isArray(next.messages)) {
    next.messages = next.messages.map((message) => {
      if (!isObject(message) || !Array.isArray(message.content)) {
        return message;
      }
      const content: unknown[] = [];
      for (const block of message.content) {
        if (!isObject(block)) {
          content.push(block);
          continue;
        }
        if (block.type === 'thinking' || block.type === 'redacted_thinking') {
          continue;
        }
        if ('signature' in block) {
          const cleaned = { ...block };
          delete cleaned.signature;
          content.push(cleaned);
          continue;
        }
        content.push(block);
      }
      return { ...message, content };
    });
  }

  if (shouldRemoveTopLevelThinking(next)) {
    delete next.thinking;
  }

  return next;
}

function shouldRemoveTopLevelThinking(body: Record<string, unknown>): boolean {
  if (!isObject(body.thinking)) {
    return false;
  }
  if (!Array.isArray(body.messages) || body.messages.length === 0) {
    return false;
  }
  const last = body.messages[body.messages.length - 1];
  if (!isObject(last) || last.role !== 'assistant') {
    return false;
  }
  if (!Array.isArray(last.content) || last.content.length === 0) {
    return true;
  }
  const first = last.content[0];
  return !(isObject(first) && (first.type === 'thinking' || first.type === 'redacted_thinking'));
}

export function applyThinkingBudgetFix(body: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...body };
  if (isObject(next.thinking) && next.thinking.type === 'adaptive') {
    return next;
  }
  const thinking: Record<string, unknown> = isObject(next.thinking) ? { ...next.thinking } : {};
  thinking.type = 'enabled';
  thinking.budget_tokens = MAX_THINKING_BUDGET;
  next.thinking = thinking;
  const maxTokens = typeof next.max_tokens === 'number' ? next.max_tokens : undefined;
  if (maxTokens === undefined || maxTokens < MIN_MAX_TOKENS_FOR_BUDGET) {
    next.max_tokens = MAX_TOKENS_VALUE;
  }
  return next;
}

export function shouldHeuristicStripImages(
  settings: GatewayRectifierSettings,
  model: string
): boolean {
  return (
    settings.enabled &&
    settings.unsupportedImageDowngrade &&
    settings.heuristicTextOnlyModels &&
    isLikelyTextOnlyModel(model)
  );
}

export function applyPreflightRectifiers(
  body: Record<string, unknown>,
  settings: GatewayRectifierSettings,
  model: string
): Record<string, unknown> {
  if (!settings.enabled || !settings.unsupportedImageDowngrade) {
    return body;
  }
  if (!shouldHeuristicStripImages(settings, model)) {
    return body;
  }
  if (!containsImageBlocks(body)) {
    return body;
  }
  return downgradeUnsupportedImages(body);
}

export type RectifierRetryKind = 'thinking_signature' | 'thinking_budget' | 'unsupported_image';

function extractErrorText(errorText: string): string {
  const trimmed = errorText.trim();
  if (!trimmed) {
    return '';
  }
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    const error = isObject(parsed.error) ? parsed.error : parsed;
    const parts = [error.message, error.type, error.code, parsed.message]
      .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
      .join(' ');
    return parts || trimmed;
  } catch {
    return trimmed;
  }
}

export function shouldRectifyThinkingSignature(
  errorText: string,
  settings: GatewayRectifierSettings
): boolean {
  if (!settings.enabled || !settings.thinkingSignature) {
    return false;
  }
  const lower = extractErrorText(errorText).toLowerCase();
  if (!lower) {
    return false;
  }
  if (
    lower.includes('invalid') &&
    lower.includes('signature') &&
    lower.includes('thinking') &&
    lower.includes('block')
  ) {
    return true;
  }
  if (
    lower.includes('thought signature') &&
    (lower.includes('not valid') || lower.includes('invalid'))
  ) {
    return true;
  }
  if (lower.includes('must start with a thinking block')) {
    return true;
  }
  if (
    lower.includes('expected') &&
    (lower.includes('thinking') || lower.includes('redacted_thinking')) &&
    lower.includes('found') &&
    lower.includes('tool_use')
  ) {
    return true;
  }
  if (lower.includes('signature') && lower.includes('field required')) {
    return true;
  }
  if (lower.includes('signature') && lower.includes('extra inputs are not permitted')) {
    return true;
  }
  if (
    (lower.includes('thinking') || lower.includes('redacted_thinking')) &&
    lower.includes('cannot be modified')
  ) {
    return true;
  }
  if (
    lower.includes('非法请求') ||
    lower.includes('illegal request') ||
    lower.includes('invalid request')
  ) {
    return true;
  }
  return false;
}

export function shouldRectifyThinkingBudget(
  errorText: string,
  settings: GatewayRectifierSettings
): boolean {
  if (!settings.enabled || !settings.thinkingBudget) {
    return false;
  }
  const lower = extractErrorText(errorText).toLowerCase();
  const hasBudgetTokensReference =
    lower.includes('budget_tokens') || lower.includes('budget tokens');
  const hasThinkingReference = lower.includes('thinking');
  const has1024Constraint =
    lower.includes('greater than or equal to 1024') ||
    lower.includes('>= 1024') ||
    (lower.includes('1024') && lower.includes('input should be'));
  return hasBudgetTokensReference && hasThinkingReference && has1024Constraint;
}

export function isUnsupportedImageError(
  status: number,
  errorText: string,
  settings: GatewayRectifierSettings
): boolean {
  if (!settings.enabled || !settings.unsupportedImageDowngrade) {
    return false;
  }
  if (![400, 415, 422, 501].includes(status)) {
    return false;
  }
  const lower = extractErrorText(errorText).toLowerCase();
  if (lower.includes('only support text') || lower.includes('only supports text')) {
    return true;
  }
  const mentionsImage =
    lower.includes('image') ||
    lower.includes('vision') ||
    lower.includes('multimodal') ||
    lower.includes('multi-modal') ||
    lower.includes('modality') ||
    lower.includes('modalities') ||
    lower.includes('media') ||
    lower.includes('attachment');
  if (!mentionsImage) {
    return false;
  }
  const hints = [
    'unsupported',
    'not supported',
    'does not support',
    "doesn't support",
    'do not support',
    "don't support",
    'text only',
    'text-only',
    'invalid content type',
    'invalid message content',
    'unknown variant',
    'unknown content type',
    'unrecognized content type',
    'cannot process',
    'cannot handle',
    "can't process",
    "can't handle",
    'unable to process',
  ];
  return hints.some((hint) => lower.includes(hint));
}

export function classifyRectifierRetry(
  status: number,
  errorText: string,
  settings: GatewayRectifierSettings,
  body?: Record<string, unknown>
): RectifierRetryKind | null {
  if (!settings.enabled || status < 400) {
    return null;
  }
  if (shouldRectifyThinkingBudget(errorText, settings)) {
    return 'thinking_budget';
  }
  if (shouldRectifyThinkingSignature(errorText, settings)) {
    return 'thinking_signature';
  }
  if (
    isUnsupportedImageError(status, errorText, settings) &&
    (!body || containsImageBlocks(body))
  ) {
    return 'unsupported_image';
  }
  return null;
}

export function applyRectifierRetryFix(
  body: Record<string, unknown>,
  kind: RectifierRetryKind
): Record<string, unknown> {
  if (kind === 'thinking_signature') {
    return stripIncompatibleThinking(body);
  }
  if (kind === 'thinking_budget') {
    return applyThinkingBudgetFix(body);
  }
  return downgradeUnsupportedImages(body);
}

export function rectifierFixChanged(
  before: Record<string, unknown>,
  after: Record<string, unknown>
): boolean {
  return JSON.stringify(before) !== JSON.stringify(after);
}
