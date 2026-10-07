export type SkillMarkdownParts = {
  meta: Record<string, unknown> | null;
  body: string;
  sentinel?: 'empty' | 'meta-only';
};

const META_ONLY = '__SKILL_MD_META_ONLY__';

function parseSimpleYamlMap(raw: string): Record<string, unknown> | null {
  const lines = raw.replace(/\t/g, '  ').split('\n');
  const root: Record<string, unknown> = {};
  const stack: { indent: number; obj: Record<string, unknown> }[] = [{ indent: -1, obj: root }];
  const current = () => stack[stack.length - 1];

  for (const line of lines) {
    if (!line.trim() || line.trimStart().startsWith('#')) {
      continue;
    }
    const indent = line.length - line.trimStart().length;
    const trimmed = line.trim();
    const sep = trimmed.indexOf(':');
    if (sep < 0) {
      return null;
    }
    const key = trimmed.slice(0, sep).trim();
    const rest = trimmed.slice(sep + 1).trim();
    if (!key) {
      return null;
    }
    while (stack.length > 1 && indent <= current().indent) {
      stack.pop();
    }
    if (rest === '') {
      const child: Record<string, unknown> = {};
      current().obj[key] = child;
      stack.push({ indent, obj: child });
      continue;
    }
    const unquoted =
      (rest.startsWith('"') && rest.endsWith('"')) || (rest.startsWith("'") && rest.endsWith("'"))
        ? rest.slice(1, -1)
        : rest;
    current().obj[key] = unquoted;
  }

  return root;
}

export function parseSkillMarkdown(text: string | null | undefined): SkillMarkdownParts {
  if (text === undefined || text === null || text === '') {
    return { meta: null, body: '', sentinel: 'empty' };
  }
  if (text === META_ONLY) {
    return { meta: null, body: '', sentinel: 'meta-only' };
  }

  const normalized = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n');
  const match = normalized.match(/^---\n([\s\S]*?)\n---[ \t]*\n?/);
  if (!match) {
    const body = normalized.trim();
    return { meta: null, body, sentinel: body ? undefined : 'empty' };
  }

  const meta = parseSimpleYamlMap(match[1]);
  const body = normalized.slice(match[0].length).trim();
  if (!body && (!meta || Object.keys(meta).length === 0)) {
    return { meta: null, body: '', sentinel: 'empty' };
  }
  if (!body) {
    return { meta, body: '', sentinel: 'meta-only' };
  }
  return { meta, body };
}

export function stringifyMetaValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (Array.isArray(value)) {
    return value.map((item) => stringifyMetaValue(item)).filter(Boolean).join(', ');
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, child]) => `${key}: ${stringifyMetaValue(child)}`)
      .join(' · ');
  }
  return String(value);
}
