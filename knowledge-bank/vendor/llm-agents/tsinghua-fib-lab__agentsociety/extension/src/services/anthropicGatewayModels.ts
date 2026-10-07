import type { AnthropicRoleMappingUpstream } from './anthropicModelMapping';

export const CLAUDE_ROLE_ROUTE_IDS = {
  sonnet: 'claude-sonnet-4-6',
  opus: 'claude-opus-4-6',
  fable: 'claude-fable-5',
  haiku: 'claude-haiku-4-5',
} as const;

export const CLAUDE_STANDARD_CONTEXT_WINDOW = 200_000;
export const CLAUDE_ONE_M_CONTEXT_WINDOW = 1_048_576;
const ONE_M_SUFFIX = '[1M]';

type RoleSpec = {
  routeId: string;
  requestedModel?: string;
  displayName?: string;
  declare1m?: boolean;
};

function buildRoleEntry(
  routeId: string,
  requestedModel: string | undefined,
  displayName: string | undefined,
  declare1m: boolean | undefined
): RoleSpec | undefined {
  const model = requestedModel?.trim();
  if (!model) {
    return undefined;
  }
  return {
    routeId,
    requestedModel: model,
    displayName: displayName?.trim() || model,
    declare1m: Boolean(declare1m),
  };
}

function collectRoleSpecs(upstream: AnthropicRoleMappingUpstream & {
  sonnetDisplayName?: string;
  opusDisplayName?: string;
  fableDisplayName?: string;
  haikuDisplayName?: string;
}): RoleSpec[] {
  const roles = [
    buildRoleEntry(
      CLAUDE_ROLE_ROUTE_IDS.sonnet,
      upstream.sonnetModel,
      upstream.sonnetDisplayName,
      upstream.declareSonnet1m
    ),
    buildRoleEntry(
      CLAUDE_ROLE_ROUTE_IDS.opus,
      upstream.opusModel,
      upstream.opusDisplayName,
      upstream.declareOpus1m
    ),
    buildRoleEntry(
      CLAUDE_ROLE_ROUTE_IDS.fable,
      upstream.fableModel,
      upstream.fableDisplayName,
      upstream.declareFable1m
    ),
    buildRoleEntry(
      CLAUDE_ROLE_ROUTE_IDS.haiku,
      upstream.haikuModel,
      upstream.haikuDisplayName,
      false
    ),
  ];
  return roles.filter((role): role is RoleSpec => Boolean(role));
}

export function buildAnthropicGatewayModelsResponse(
  upstream: AnthropicRoleMappingUpstream & {
    sonnetDisplayName?: string;
    opusDisplayName?: string;
    fableDisplayName?: string;
    haikuDisplayName?: string;
  }
): Record<string, unknown> | null {
  const roles = collectRoleSpecs(upstream);
  if (roles.length === 0) {
    return null;
  }

  const data: Array<Record<string, unknown>> = [];
  for (const role of roles) {
    data.push({
      id: role.routeId,
      display_name: role.displayName,
      context_window: CLAUDE_STANDARD_CONTEXT_WINDOW,
    });
    if (role.declare1m) {
      data.push({
        id: `${role.routeId}${ONE_M_SUFFIX}`,
        display_name: role.displayName,
        context_window: CLAUDE_ONE_M_CONTEXT_WINDOW,
      });
    }
  }

  return {
    object: 'list',
    data,
  };
}
