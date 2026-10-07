import type { AiCliGatewayUpstream } from './aiCliGatewayUpstream';

const ONE_M_CONTEXT_MARKER = '[1M]';

function stripOneMContextMarker(model: string): string {
  const trimmed = model.trimEnd();
  const suffix = trimmed.slice(-ONE_M_CONTEXT_MARKER.length);
  if (suffix.toLowerCase() !== ONE_M_CONTEXT_MARKER.toLowerCase()) {
    return model;
  }
  return trimmed.slice(0, -ONE_M_CONTEXT_MARKER.length).trimEnd();
}

function requestedUsesOneMContext(requestedModel: string): boolean {
  const trimmed = requestedModel.trimEnd();
  const suffix = trimmed.slice(-ONE_M_CONTEXT_MARKER.length);
  return suffix.toLowerCase() === ONE_M_CONTEXT_MARKER.toLowerCase();
}

export type AnthropicRoleMappingUpstream = Pick<
  AiCliGatewayUpstream,
  | 'model'
  | 'sonnetModel'
  | 'opusModel'
  | 'fableModel'
  | 'haikuModel'
  | 'declareSonnet1m'
  | 'declareOpus1m'
  | 'declareFable1m'
>;

function resolveRoleUpstreamModel(
  normalizedRequested: string,
  upstream: AnthropicRoleMappingUpstream
): string | undefined {
  const lower = normalizedRequested.toLowerCase();

  if (lower.includes('fable')) {
    return upstream.fableModel?.trim();
  }
  if (lower.includes('haiku')) {
    return upstream.haikuModel?.trim() || upstream.model?.trim();
  }
  if (lower.includes('opus')) {
    return upstream.opusModel?.trim() || upstream.model?.trim();
  }
  if (lower.includes('sonnet')) {
    return upstream.sonnetModel?.trim() || upstream.model?.trim();
  }
  return upstream.model?.trim();
}

export function resolveAnthropicGatewayModel(
  requestedModel: unknown,
  upstream: AnthropicRoleMappingUpstream
): string {
  const requested = typeof requestedModel === 'string' ? requestedModel.trim() : '';
  const normalizedRequested = stripOneMContextMarker(requested);
  const mapped = resolveRoleUpstreamModel(normalizedRequested, upstream);
  if (mapped) {
    return stripOneMContextMarker(mapped);
  }
  return normalizedRequested;
}

export function applyAnthropicModelMapping(
  body: Record<string, unknown>,
  upstream: AnthropicRoleMappingUpstream
): { body: Record<string, unknown>; originalModel?: string; mappedModel?: string } {
  const originalModel = typeof body.model === 'string' ? body.model : undefined;
  if (!originalModel) {
    return { body };
  }

  const mappedModel = resolveAnthropicGatewayModel(originalModel, upstream);
  if (!mappedModel || mappedModel === originalModel) {
    return { body, originalModel };
  }

  return {
    body: { ...body, model: mappedModel },
    originalModel,
    mappedModel,
  };
}

export function requestedModelUsesOneMContext(requestedModel: unknown): boolean {
  return typeof requestedModel === 'string' && requestedUsesOneMContext(requestedModel);
}
