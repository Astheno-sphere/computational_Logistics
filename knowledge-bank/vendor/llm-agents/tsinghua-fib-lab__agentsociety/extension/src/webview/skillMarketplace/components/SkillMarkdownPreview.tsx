import * as React from 'react';
import { Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import type { VscodeThemePalette } from '../../theme';
import { MarkdownRenderer } from '../../components/MarkdownRenderer';
import { parseSkillMarkdown, stringifyMetaValue } from '../parseSkillMarkdown';

const { Text } = Typography;

export type SkillFact = {
  label: string;
  value: React.ReactNode;
};

type Props = {
  content: string | null | undefined;
  palette: VscodeThemePalette;
  isDark: boolean;
  extraFacts?: SkillFact[];
};

const SKIP_KEYS = new Set(['name', 'description', 'version']);
const CONSUMED_KEYS = new Set(['name', 'description', 'script', 'hooks', 'version']);

const KNOWN_LABELS: Record<string, string> = {
  license: 'skillManagement.skillLicense',
  compatibility: 'skillManagement.detailCompat',
  'allowed-tools': 'skillManagement.skillAllowedTools',
  allowed_tools: 'skillManagement.skillAllowedTools',
  author: 'skillManagement.skillAuthor',
  homepage: 'skillManagement.skillHomepage',
};

function isPathLike(value: string): boolean {
  return value.includes('/') || value.endsWith('.py') || value.endsWith('.ts') || value.endsWith('.js');
}

function Mono({ children }: { children: React.ReactNode }) {
  return (
    <Text
      style={{
        fontSize: 12,
        lineHeight: 1.5,
        wordBreak: 'break-word',
        fontFamily: 'var(--vscode-editor-font-family, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace)',
      }}
    >
      {children}
    </Text>
  );
}

function FactRow({ label, value }: SkillFact) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '88px 1fr',
        columnGap: 10,
        alignItems: 'start',
      }}
    >
      <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.55, paddingTop: 1 }}>
        {label}
      </Text>
      <div style={{ minWidth: 0, fontSize: 12, lineHeight: 1.55 }}>{value}</div>
    </div>
  );
}

export function SkillMarkdownPreview({ content, palette, isDark, extraFacts }: Props) {
  const { t } = useTranslation();
  const parts = React.useMemo(() => parseSkillMarkdown(content), [content]);

  const facts = React.useMemo((): SkillFact[] => {
    const rows: SkillFact[] = [...(extraFacts ?? [])];
    const meta = parts.meta;
    if (!meta) {
      return rows;
    }

    const script = stringifyMetaValue(meta.script);
    if (script) {
      rows.push({ label: t('skillManagement.detailScript'), value: <Mono>{script}</Mono> });
    }

    const hooks = meta.hooks;
    if (hooks && typeof hooks === 'object' && !Array.isArray(hooks)) {
      const entries = Object.entries(hooks as Record<string, unknown>).filter(([, target]) => target != null && target !== '');
      if (entries.length > 0) {
        rows.push({
          label: t('skillManagement.skillLifecycle'),
          value: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {entries.map(([event, target]) => {
                const hookLabel = t(`skillManagement.skillHook.${event}`, { defaultValue: event });
                return (
                  <div key={event} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'baseline' }}>
                    <Text style={{ fontSize: 12, fontWeight: 600 }}>{hookLabel}</Text>
                    <Mono>{stringifyMetaValue(target)}</Mono>
                  </div>
                );
              })}
            </div>
          ),
        });
      }
    } else if (hooks) {
      rows.push({ label: t('skillManagement.skillLifecycle'), value: <Mono>{stringifyMetaValue(hooks)}</Mono> });
    }

    const preferred = ['license', 'compatibility', 'allowed-tools', 'allowed_tools', 'author', 'homepage'];
    const rest = Object.keys(meta).filter((key) => !CONSUMED_KEYS.has(key) && !SKIP_KEYS.has(key));
    const ordered = [...preferred.filter((key) => rest.includes(key)), ...rest.filter((key) => !preferred.includes(key))];

    for (const key of ordered) {
      const raw = stringifyMetaValue(meta[key]);
      if (!raw) {
        continue;
      }
      const labelKey = KNOWN_LABELS[key];
      rows.push({
        label: labelKey ? t(labelKey) : key,
        value: key === 'homepage' || isPathLike(raw)
          ? <Mono>{raw}</Mono>
          : <Text style={{ fontSize: 12, wordBreak: 'break-word' }}>{raw}</Text>,
      });
    }

    return rows;
  }, [extraFacts, parts.meta, t]);

  if (parts.sentinel === 'empty' && facts.length === 0) {
    return (
      <Text type="secondary" style={{ fontSize: 12 }}>
        {t('skillManagement.detailNoMarkdownBody')}
      </Text>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {facts.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {facts.map((fact) => (
            <FactRow key={fact.label} label={fact.label} value={fact.value} />
          ))}
        </div>
      ) : null}

      {parts.body ? (
        <div
          style={{
            borderTop: facts.length > 0 ? `1px solid ${palette.panelBorder}` : undefined,
            paddingTop: facts.length > 0 ? 12 : 0,
            maxHeight: 280,
            overflow: 'auto',
          }}
        >
          <MarkdownRenderer content={parts.body} isDark={isDark} style={{ fontSize: 12 }} />
        </div>
      ) : null}
    </div>
  );
}
