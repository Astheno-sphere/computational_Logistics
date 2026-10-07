/**
 * Classify backend skill ``source`` / ``skill_id`` into built-in | custom | env.
 *
 * Prefer the registry ``source`` field; ``source_label`` is a filesystem path
 * and must not drive classification.
 */

export type AgentSkillSourceKind = 'built-in' | 'custom' | 'env';

export type AgentSkillSourceFields = {
  source?: string;
  skill_id?: string;
};

export function normalizeAgentSkillSource(source: string | undefined): AgentSkillSourceKind {
  const raw = (source ?? '').trim().toLowerCase();
  if (raw === 'built-in' || raw.startsWith('built-in@') || raw.startsWith('built-in:')) {
    return 'built-in';
  }
  if (raw === 'env' || raw.startsWith('env:') || raw.startsWith('env@')) {
    return 'env';
  }
  if (raw === 'custom' || raw.startsWith('custom@') || raw.startsWith('custom:')) {
    return 'custom';
  }
  return 'custom';
}

export function resolveAgentSkillSourceKind(skill: AgentSkillSourceFields): AgentSkillSourceKind {
  const fromSource = skill.source?.trim();
  if (fromSource) {
    return normalizeAgentSkillSource(fromSource);
  }
  const id = skill.skill_id?.trim() ?? '';
  if (id.startsWith('built-in@') || id.startsWith('built-in:')) {
    return 'built-in';
  }
  if (id.startsWith('env@') || id.startsWith('env:')) {
    return 'env';
  }
  return 'custom';
}

export function partitionAgentSkillsBySource<T extends AgentSkillSourceFields>(
  skills: readonly T[]
): { builtin: T[]; custom: T[]; env: T[] } {
  const builtin: T[] = [];
  const custom: T[] = [];
  const env: T[] = [];
  for (const skill of skills) {
    const kind = resolveAgentSkillSourceKind(skill);
    if (kind === 'built-in') {
      builtin.push(skill);
    } else if (kind === 'env') {
      env.push(skill);
    } else {
      custom.push(skill);
    }
  }
  return { builtin, custom, env };
}

export function isBuiltinAgentSkill(skill: AgentSkillSourceFields): boolean {
  return resolveAgentSkillSourceKind(skill) === 'built-in';
}
