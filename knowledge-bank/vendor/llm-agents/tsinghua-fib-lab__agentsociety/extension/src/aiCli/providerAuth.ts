import {
  inferApiKindFromBaseUrl,
  isOfficialAnthropicBaseUrl,
  isOfficialOpenAiBaseUrl,
  type AiCliApiKind,
} from './officialEndpoints';

export type AiCliAuthMode = 'subscription' | 'api';

export type AiCliProviderAuthFields = {
  baseUrl: string;
  apiKey: string;
  apiKind?: AiCliApiKind;
  authMode?: AiCliAuthMode;
};

export function inferProviderAuthMode(provider: AiCliProviderAuthFields): AiCliAuthMode {
  if (provider.authMode === 'subscription' || provider.authMode === 'api') {
    return provider.authMode;
  }
  if (provider.apiKey.trim()) {
    return 'api';
  }
  const kind = provider.apiKind ?? inferApiKindFromBaseUrl(provider.baseUrl);
  if (kind === 'openai' && isOfficialOpenAiBaseUrl(provider.baseUrl)) {
    return 'subscription';
  }
  if (kind !== 'openai' && isOfficialAnthropicBaseUrl(provider.baseUrl)) {
    return 'subscription';
  }
  return 'api';
}

export function isOfficialSubscriptionProvider(provider: AiCliProviderAuthFields): boolean {
  return inferProviderAuthMode(provider) === 'subscription';
}

export function providerHasConfiguredCredentials(provider: AiCliProviderAuthFields): boolean {
  if (isOfficialSubscriptionProvider(provider)) {
    return true;
  }
  return Boolean(provider.apiKey.trim());
}

export function providerHasApiUpstream(provider: AiCliProviderAuthFields): boolean {
  return inferProviderAuthMode(provider) === 'api' && Boolean(provider.apiKey.trim());
}

/**
 * Whether a provider can serve as an API upstream for a CLI role.
 *
 * Claude can use Anthropic upstreams and OpenAI-compatible ones (gateway translates).
 * Codex only uses OpenAI-compatible API upstreams.
 */
export function providerEligibleForRoleUpstream(
  provider: AiCliProviderAuthFields,
  role: 'claude' | 'codex'
): boolean {
  if (!providerHasApiUpstream(provider)) {
    return false;
  }
  if (role === 'claude') {
    return true;
  }
  const kind = provider.apiKind ?? inferApiKindFromBaseUrl(provider.baseUrl);
  return kind === 'openai';
}

export function countApiUpstreamsForRole(
  providers: readonly AiCliProviderAuthFields[],
  role: 'claude' | 'codex'
): number {
  return providers.filter((provider) => providerEligibleForRoleUpstream(provider, role)).length;
}

export type AiCliProviderRoleFlags = {
  failoverClaude?: boolean;
  failoverCodex?: boolean;
};

/**
 * Drop role flags that cannot apply for the provider's apiKind.
 * Uses apiKind only (not apiKey) so metadata hydrate before secrets stays stable.
 */
export function clampProviderRoleFlags<T extends AiCliProviderAuthFields & AiCliProviderRoleFlags>(
  provider: T
): T {
  const apiKind = provider.apiKind ?? inferApiKindFromBaseUrl(provider.baseUrl);
  return {
    ...provider,
    apiKind,
    failoverCodex: Boolean(provider.failoverCodex) && apiKind === 'openai',
  };
}
