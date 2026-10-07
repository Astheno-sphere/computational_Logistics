import { isAllowedSkillSourceBaseUrl } from './urlSafety';

export type ParsedSkillSource = {
  owner: string;
  repo: string;
  branch?: string;
  skillsPath?: string;
  platform?: 'github' | 'gitlab' | 'gitee';
  baseUrl?: string;
};

export type ParseSkillSourceError = 'empty' | 'invalid';

export type ParseSkillSourceResult =
  | { ok: true; source: ParsedSkillSource }
  | { ok: false; error: ParseSkillSourceError };

const TREE_MARKERS = new Set(['tree', 'blob', 'src', 'raw']);

function stripGitSuffix(value: string): string {
  return value.replace(/\.git$/i, '');
}

function inferPlatform(host: string): NonNullable<ParsedSkillSource['platform']> {
  const hostname = host.toLowerCase().replace(/^www\./, '');
  if (hostname === 'github.com' || hostname.endsWith('.github.com')) {
    return 'github';
  }
  if (hostname === 'gitee.com' || hostname.endsWith('.gitee.com')) {
    return 'gitee';
  }
  return 'gitlab';
}

function defaultHost(platform: NonNullable<ParsedSkillSource['platform']>): string {
  if (platform === 'gitlab') {
    return 'gitlab.com';
  }
  if (platform === 'gitee') {
    return 'gitee.com';
  }
  return 'github.com';
}

function originForHost(host: string): string {
  return `https://${host.replace(/^www\./, '')}`;
}

function needsBaseUrl(host: string, platform: NonNullable<ParsedSkillSource['platform']>): boolean {
  return host.toLowerCase().replace(/^www\./, '') !== defaultHost(platform);
}

function applyPathOverride(source: ParsedSkillSource, pathOverride?: string): ParsedSkillSource {
  const skillsPath = (pathOverride ?? '').trim().replace(/^\/+|\/+$/g, '');
  if (!skillsPath) {
    return source;
  }
  return { ...source, skillsPath };
}

function takeOwnerRepo(
  segments: string[],
  platform: NonNullable<ParsedSkillSource['platform']>,
): { owner: string; repo: string; rest: string[] } | null {
  const dash = segments.indexOf('-');
  if (platform === 'gitlab' && dash >= 2) {
    const repo = segments[dash - 1];
    const owner = segments.slice(0, dash - 1).join('/');
    if (!owner || !repo) {
      return null;
    }
    return { owner, repo, rest: segments.slice(dash + 1) };
  }
  if (platform === 'github' || platform === 'gitee') {
    if (segments.length < 2) {
      return null;
    }
    return { owner: segments[0], repo: segments[1], rest: segments.slice(2) };
  }
  if (segments.length < 2) {
    return null;
  }
  return {
    owner: segments.slice(0, -1).join('/'),
    repo: segments[segments.length - 1],
    rest: [],
  };
}

function consumeTreePath(rest: string[]): { branch: string; skillsPath?: string } {
  if (rest.length === 0) {
    return { branch: 'main' };
  }
  const marker = rest[0];
  if (TREE_MARKERS.has(marker) && rest.length >= 2) {
    const branch = rest[1];
    const leftover = rest.slice(2);
    if (marker === 'blob' && leftover.length > 0) {
      leftover.pop();
    }
    const skillsPath = leftover.join('/') || undefined;
    return { branch, skillsPath };
  }
  return { branch: 'main', skillsPath: rest.join('/') || undefined };
}

function fromHostAndPath(
  host: string,
  repoPath: string,
  pathOverride?: string,
): ParseSkillSourceResult {
  const hostname = host.replace(/^www\./, '');
  const platform = inferPlatform(hostname);
  const segments = stripGitSuffix(repoPath).replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
  const parsed = takeOwnerRepo(segments, platform);
  if (!parsed) {
    return { ok: false, error: 'invalid' };
  }
  const tree = consumeTreePath(parsed.rest);
  const source: ParsedSkillSource = {
    owner: parsed.owner,
    repo: parsed.repo,
    branch: tree.branch || 'main',
    platform,
  };
  if (tree.skillsPath) {
    source.skillsPath = tree.skillsPath;
  }
  if (needsBaseUrl(hostname, platform)) {
    const origin = originForHost(hostname);
    if (!isAllowedSkillSourceBaseUrl(origin)) {
      return { ok: false, error: 'invalid' };
    }
    source.baseUrl = origin;
  }
  return { ok: true, source: applyPathOverride(source, pathOverride) };
}

/**
 * Parse a user-entered skill repository URL or ``owner/repo`` shorthand.
 */
export function parseSkillSourceInput(raw: string, pathOverride?: string): ParseSkillSourceResult {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { ok: false, error: 'empty' };
  }

  const ssh = trimmed.match(/^git@([^:]+):(.+)$/i);
  if (ssh) {
    return fromHostAndPath(ssh[1], ssh[2], pathOverride);
  }

  let candidate = trimmed;
  if (!/^[a-z][a-z0-9+.-]*:/i.test(candidate) && candidate.includes('.')) {
    candidate = `https://${candidate}`;
  }

  if (/^https?:\/\//i.test(candidate)) {
    let url: URL;
    try {
      url = new URL(candidate);
    } catch {
      return { ok: false, error: 'invalid' };
    }
    if (url.protocol !== 'https:') {
      return { ok: false, error: 'invalid' };
    }
    return fromHostAndPath(url.hostname, url.pathname, pathOverride);
  }

  const parts = stripGitSuffix(trimmed).split('/').filter(Boolean);
  if (parts.length >= 2 && !trimmed.includes(' ') && !trimmed.includes(':')) {
    const source: ParsedSkillSource = {
      owner: parts[0],
      repo: parts[1],
      branch: 'main',
      platform: 'github',
    };
    const extra = parts.slice(2).join('/');
    if (extra) {
      source.skillsPath = extra;
    }
    return { ok: true, source: applyPathOverride(source, pathOverride) };
  }

  return { ok: false, error: 'invalid' };
}

export function skillSourceKey(source: ParsedSkillSource): string {
  return [
    source.platform || 'github',
    source.baseUrl || '',
    source.owner,
    source.repo,
    source.branch || 'main',
    source.skillsPath || '',
  ].join('|');
}

export function formatSkillSourceHost(source: ParsedSkillSource): string {
  if (source.baseUrl) {
    try {
      return new URL(source.baseUrl).host;
    } catch {
      return source.baseUrl.replace(/^https?:\/\//, '').replace(/\/+$/, '');
    }
  }
  return defaultHost(source.platform || 'github');
}

export function formatSkillSourceRepo(source: ParsedSkillSource): string {
  return `${formatSkillSourceHost(source)}/${source.owner}/${source.repo}`;
}
