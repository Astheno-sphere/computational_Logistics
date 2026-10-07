import * as React from 'react';
import { Button, Collapse, Input, Space, Tag, Tooltip, Typography, message } from 'antd';
import { DeleteOutlined, PlusOutlined, UndoOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VscodeThemePalette } from '../../theme';
import type { SkillSourceConfig } from '../types';
import {
  formatSkillSourceRepo,
  parseSkillSourceInput,
  skillSourceKey,
} from '../../../skillMarketplace/parseSkillSourceInput';
import { ListCard } from './ListCard';
import { SKILL_UI } from '../uiTokens';

const { Text } = Typography;

type Props = {
  palette: VscodeThemePalette;
  sources: SkillSourceConfig[];
  defaultSources: SkillSourceConfig[];
  loading: boolean;
  githubToken: string;
  onGithubTokenChange: (token: string) => void;
  onSaveGithubToken: () => void;
  onSaveSources: (sources: SkillSourceConfig[]) => void;
};

function platformLabel(platform: SkillSourceConfig['platform']): string {
  if (platform === 'gitlab') {
    return 'GitLab';
  }
  if (platform === 'gitee') {
    return 'Gitee';
  }
  return 'GitHub';
}

function isDefaultSource(source: SkillSourceConfig, defaults: SkillSourceConfig[]): boolean {
  const key = skillSourceKey(source);
  return defaults.some((item) => skillSourceKey(item) === key);
}

export function SourcesConfigPanel({
  palette,
  sources,
  defaultSources,
  loading,
  githubToken,
  onGithubTokenChange,
  onSaveGithubToken,
  onSaveSources,
}: Props) {
  const { t } = useTranslation();
  const [repoInput, setRepoInput] = React.useState('');
  const [pathInput, setPathInput] = React.useState('');
  const hasDefaults = defaultSources.length > 0;

  const handleAdd = () => {
    const parsed = parseSkillSourceInput(repoInput, pathInput);
    if (!parsed.ok) {
      message.error(t('skillManagement.sourceParseInvalid'));
      return;
    }
    if (sources.some((item) => skillSourceKey(item) === skillSourceKey(parsed.source))) {
      message.warning(t('skillManagement.sourceDuplicate'));
      return;
    }
    setRepoInput('');
    setPathInput('');
    onSaveSources([...sources, parsed.source]);
  };

  return (
    <div>
      <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 12, lineHeight: 1.55 }}>
        {hasDefaults
          ? t('skillManagement.sourcesConfigHintWithDefault')
          : t('skillManagement.sourcesConfigHint')}
      </Text>

      <div
        style={{
          padding: 12,
          marginBottom: 16,
          borderRadius: SKILL_UI.radius.sm,
          border: `1px solid ${palette.panelBorder}`,
          background: palette.surfaceBackground,
        }}
      >
        <Text strong style={{ display: 'block', fontSize: 13, marginBottom: 8 }}>
          {t('skillManagement.sourceUrlLabel')}
        </Text>
        <Input
          value={repoInput}
          onChange={(e) => setRepoInput(e.target.value)}
          onPressEnter={handleAdd}
          placeholder={t('skillManagement.sourceUrlPlaceholder')}
          allowClear
        />
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 10, marginBottom: 6 }}>
          {t('skillManagement.sourcePathHint')}
        </Text>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onPressEnter={handleAdd}
            placeholder={t('skillManagement.sourcePathPlaceholder')}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd} loading={loading}>
            {t('skillManagement.addSource')}
          </Button>
        </Space.Compact>
      </div>

      <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong style={{ fontSize: 13 }}>{t('skillManagement.sourcesList')}</Text>
        {hasDefaults ? (
          <Tooltip title={t('skillManagement.resetToDefaultTooltip')}>
            <Button
              size="small"
              icon={<UndoOutlined />}
              onClick={() => onSaveSources([...defaultSources])}
              loading={loading}
            >
              {t('skillManagement.resetToDefault')}
            </Button>
          </Tooltip>
        ) : null}
      </div>

      {sources.length === 0 ? (
        <Text type="secondary" style={{ display: 'block', fontSize: 12, padding: '12px 0' }}>
          {t('skillManagement.noSources')}
        </Text>
      ) : (
        sources.map((source, index) => {
          const builtin = isDefaultSource(source, defaultSources);
          return (
            <ListCard
              key={skillSourceKey(source) || `${index}`}
              palette={palette}
              hoverable={false}
              style={{ marginBottom: 8 }}
              bodyStyle={{ padding: '10px 12px' }}
            >
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                    <Tag style={{ margin: 0 }}>{platformLabel(source.platform)}</Tag>
                    <Text strong style={{ fontSize: 13, wordBreak: 'break-all' }}>
                      {formatSkillSourceRepo(source)}
                    </Text>
                    {builtin ? (
                      <Tag color="blue" style={{ margin: 0 }}>{t('skillManagement.isDefaultSource')}</Tag>
                    ) : null}
                  </div>
                  <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 6 }}>
                    {source.skillsPath
                      ? t('skillManagement.sourceSkillsDir', { path: source.skillsPath })
                      : t('skillManagement.sourceRepoRoot')}
                    {` · ${t('skillManagement.sourceBranch')} ${source.branch || 'main'}`}
                  </Text>
                </div>
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => onSaveSources(sources.filter((_, i) => i !== index))}
                  aria-label={t('skillManagement.delete')}
                />
              </div>
            </ListCard>
          );
        })
      )}

      <Collapse
        ghost
        size="small"
        style={{ marginTop: 8 }}
        items={[{
          key: 'token',
          label: (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('skillManagement.githubTokenCollapse')}
            </Text>
          ),
          children: (
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                {t('skillManagement.githubTokenDesc')}
              </Text>
              <Input.Password
                size="small"
                value={githubToken}
                onChange={(e) => onGithubTokenChange(e.target.value)}
                placeholder="ghp_xxxx"
                style={{ marginBottom: 8 }}
              />
              <Button size="small" type="primary" ghost onClick={onSaveGithubToken}>
                {t('skillManagement.saveToken')}
              </Button>
            </div>
          ),
        }]}
      />
    </div>
  );
}
