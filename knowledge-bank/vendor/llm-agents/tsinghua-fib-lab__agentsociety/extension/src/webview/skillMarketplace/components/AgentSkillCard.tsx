import * as React from 'react';
import { Button, Dropdown, Tag, Typography } from 'antd';
import type { MenuProps } from 'antd';
import {
  ApiOutlined,
  BookOutlined,
  FolderOpenOutlined,
  MoreOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../../theme';
import type { AgentSkill, AgentSkillDetailPayload } from '../types';
import type { AgentSkillSourceKind } from '../../../agentSkillSource';
import { SkillDetailCollapse } from './SkillDetailCollapse';
import { SkillEntryCard } from './SkillEntryCard';
import { SkillMarkdownPreview } from './SkillMarkdownPreview';

const { Text } = Typography;

type Props = {
  skill: AgentSkill;
  sourceKind: AgentSkillSourceKind;
  palette: VscodeThemePalette;
  isDark: boolean;
  detail?: AgentSkillDetailPayload;
  detailLoading: boolean;
  t: TFunction;
  onOpenDoc: (skill: AgentSkill) => void;
  onOpenFolder: (path: string) => void;
  onExpandDetail: (skill: AgentSkill) => void;
};

function sourceAccent(kind: AgentSkillSourceKind, palette: VscodeThemePalette): string {
  if (kind === 'built-in') {
    return palette.linkForeground;
  }
  if (kind === 'env') {
    return palette.warningForeground ?? palette.linkForeground;
  }
  return palette.successForeground;
}

export function AgentSkillCard({
  skill,
  sourceKind,
  palette,
  isDark,
  detail,
  detailLoading,
  t,
  onOpenDoc,
  onOpenFolder,
  onExpandDetail,
}: Props) {
  const scriptText = (detail?.script ?? skill.script ?? '').trim();
  const mdBody = (detail?.skill_md ?? '').trim();
  const accent = sourceAccent(sourceKind, palette);
  const isBuiltin = sourceKind === 'built-in';

  const menuItems: MenuProps['items'] = [
    {
      key: 'doc',
      label: t('skillManagement.viewDocumentation'),
      icon: <BookOutlined />,
      disabled: !skill.has_skill_md && !mdBody,
      onClick: () => onOpenDoc(skill),
    },
    {
      key: 'folder',
      label: t('skillManagement.openFolder'),
      icon: <FolderOpenOutlined />,
      onClick: () => onOpenFolder(skill.path),
    },
  ];

  const kindTag =
    sourceKind === 'built-in'
      ? { color: 'blue' as const, label: t('skillManagement.tagAgentBackend') }
      : sourceKind === 'env'
        ? { color: 'gold' as const, label: t('skillManagement.tagAgentEnv') }
        : { color: 'green' as const, label: t('skillManagement.tagAgentRegistered') };

  const icon =
    sourceKind === 'built-in' ? (
      <ThunderboltOutlined style={{ fontSize: 18 }} />
    ) : sourceKind === 'env' ? (
      <ApiOutlined style={{ fontSize: 18 }} />
    ) : (
      <RobotOutlined style={{ fontSize: 18 }} />
    );

  return (
    <SkillEntryCard
      palette={palette}
      accent={accent}
      icon={icon}
      title={skill.name}
      tags={
        <>
          <Tag color={kindTag.color} style={{ margin: 0 }}>
            {kindTag.label}
          </Tag>
          {isBuiltin ? (
            <Tag color="blue" style={{ margin: 0 }}>
              {t('skillManagement.builtinAgentSkillTag')}
            </Tag>
          ) : null}
          {skill.has_skill_md ? (
            <Tag icon={<BookOutlined />} style={{ margin: 0 }}>
              SKILL.md
            </Tag>
          ) : null}
          {scriptText ? (
            <Tag icon={<ToolOutlined />} style={{ margin: 0 }}>
              {scriptText}
            </Tag>
          ) : null}
        </>
      }
      description={skill.description || t('skillManagement.noDescription')}
      actions={
        <Dropdown trigger={['click']} menu={{ items: menuItems }}>
          <Button type="text" size="small" icon={<MoreOutlined />} aria-label={t('skillManagement.moreActions')} />
        </Dropdown>
      }
      style={{ boxShadow: isBuiltin ? `0 4px 14px ${accent}12` : undefined }}
    >
      <SkillDetailCollapse
        panelLabel={t('skillManagement.skillDetails')}
        onPanelOpen={() => onExpandDetail(skill)}
        loading={detailLoading && !detail}
        borderColor={palette.panelBorder}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <SkillMarkdownPreview
            content={mdBody}
            palette={palette}
            isDark={isDark}
            extraFacts={[
              {
                label: t('skillManagement.detailPath'),
                value: (
                  <Text style={{ fontSize: 12, wordBreak: 'break-all' }}>
                    {detail?.path ?? skill.path}
                  </Text>
                ),
              },
            ]}
          />
        </div>
      </SkillDetailCollapse>
    </SkillEntryCard>
  );
}
