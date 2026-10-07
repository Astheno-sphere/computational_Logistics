import * as React from 'react';
import { Space, Tag, Typography } from 'antd';
import type { VscodeThemePalette } from '../../theme';
import { ListCard } from './ListCard';
import { iconBadgeStyle } from '../uiTokens';

const { Text, Title } = Typography;

export type SkillEntryCardProps = {
  palette: VscodeThemePalette;
  title: React.ReactNode;
  description?: React.ReactNode;
  tags?: React.ReactNode;
  icon?: React.ReactNode;
  accent?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  hoverable?: boolean;
  style?: React.CSSProperties;
};

export function versionTag(version?: string): React.ReactNode {
  const raw = (version ?? '').trim();
  if (!raw) {
    return null;
  }
  const label = raw.startsWith('v') ? raw : `v${raw}`;
  return (
    <Tag style={{ margin: 0, fontSize: 11, lineHeight: '18px' }}>
      {label}
    </Tag>
  );
}

export function SkillEntryCard({
  palette,
  title,
  description,
  tags,
  icon,
  accent,
  actions,
  children,
  hoverable = true,
  style,
}: SkillEntryCardProps) {
  const badgeAccent = accent ?? palette.linkForeground;

  return (
    <ListCard
      palette={palette}
      hoverable={hoverable}
      accent={accent}
      style={{ height: '100%', marginBottom: 0, ...style }}
    >
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        {icon ? <span style={iconBadgeStyle(badgeAccent)}>{icon}</span> : null}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 8,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <Title
                level={5}
                style={{ margin: 0, fontSize: 15, lineHeight: 1.3, wordBreak: 'break-word' }}
              >
                {title}
              </Title>
              {tags ? (
                <Space size={[4, 4]} wrap style={{ marginTop: 6 }}>
                  {tags}
                </Space>
              ) : null}
            </div>
            {actions ? (
              <Space wrap size={4} style={{ flex: '0 0 auto', justifyContent: 'flex-end' }}>
                {actions}
              </Space>
            ) : null}
          </div>
          {description ? (
            <Text
              type="secondary"
              style={{ display: 'block', marginTop: 10, fontSize: 13, lineHeight: 1.5 }}
            >
              {description}
            </Text>
          ) : null}
        </div>
      </div>
      {children ? <div style={{ marginTop: 8 }}>{children}</div> : null}
    </ListCard>
  );
}
