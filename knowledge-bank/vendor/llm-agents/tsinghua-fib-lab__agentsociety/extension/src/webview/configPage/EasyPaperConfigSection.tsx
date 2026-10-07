import * as React from 'react';
import { Alert, Button, Form, Input, Switch, Typography } from 'antd';
import { CopyOutlined, SaveOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import type { EasyPaperConfigValues } from './types';
import { tabBodyStyle } from './configPageStyles';

const { Text } = Typography;

export interface EasyPaperConfigSectionProps {
  t: TFunction;
  palette: VscodeThemePalette;
  form: FormInstance<EasyPaperConfigValues>;
  defaultLlmApiKey: string;
  defaultLlmApiBase: string;
  defaultLlmModel: string;
  onSave: () => void;
  /** When false, hide the section footer save button (wizard uses bottom CTA). */
  showInlineSave?: boolean;
  showIntro?: boolean;
}

export function EasyPaperConfigSection({
  t,
  defaultLlmApiKey,
  defaultLlmApiBase,
  defaultLlmModel,
  onSave,
  form,
  showInlineSave = true,
  showIntro = true,
}: EasyPaperConfigSectionProps) {
  const vlmEnabled = Boolean(Form.useWatch('vlmEnabled', form));

  const handleCopyFromAgentSociety = () => {
    form.setFieldsValue({
      llmModelName: defaultLlmModel || '',
      llmApiKey: defaultLlmApiKey || '',
      llmBaseUrl: defaultLlmApiBase || '',
      vlmEnabled: true,
      vlmModel: form.getFieldValue('vlmModel') || 'deepseek-v4-flash',
      vlmApiKey: defaultLlmApiKey || '',
      vlmBaseUrl: defaultLlmApiBase || '',
    });
  };

  return (
    <div style={tabBodyStyle}>
      {showIntro ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16, fontSize: 12 }}
          message={t('easyPaperConfig.infoTitle')}
          description={t('easyPaperConfig.infoDescription')}
        />
      ) : null}

      <Form form={form} layout="vertical" component={false}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
          {t('easyPaperConfig.llmSection')}
          <Text type="secondary" style={{ fontWeight: 400, marginLeft: 8, fontSize: 12 }}>
            {t('easyPaperConfig.llmSectionHint')}
          </Text>
        </Text>

        <div style={{ marginBottom: 12 }}>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopyFromAgentSociety}
            disabled={!defaultLlmApiKey}
          >
            {t('easyPaperConfig.copyFromAgentSociety')}
          </Button>
          {!defaultLlmApiKey ? (
            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
              {t('easyPaperConfig.copyDisabled')}
            </Text>
          ) : null}
        </div>

        <Form.Item name="llmModelName" label={t('easyPaperConfig.modelName')} style={{ marginBottom: 10 }}>
          <Input placeholder={t('easyPaperConfig.modelNamePlaceholder')} autoComplete="off" />
        </Form.Item>
        <Form.Item name="llmBaseUrl" label="Base URL" style={{ marginBottom: 10 }}>
          <Input placeholder={t('easyPaperConfig.baseUrlPlaceholder')} autoComplete="off" />
        </Form.Item>
        <Form.Item name="llmApiKey" label="API Key" style={{ marginBottom: 16 }}>
          <Input.Password placeholder={t('easyPaperConfig.apiKeyPlaceholder')} autoComplete="off" />
        </Form.Item>

        <div style={{ marginTop: 8, marginBottom: 8 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Form.Item name="vlmEnabled" valuePropName="checked" noStyle>
              <Switch size="small" />
            </Form.Item>
            <Text strong style={{ fontSize: 13 }}>{t('easyPaperConfig.vlmSection')}</Text>
            <Text type="secondary" style={{ fontSize: 11, fontWeight: 400 }}>
              {t('easyPaperConfig.vlmOptional')}
            </Text>
          </span>
        </div>
        {vlmEnabled ? (
          <>
            <Form.Item name="vlmModel" label={t('easyPaperConfig.vlmModel')} style={{ marginBottom: 10 }}>
              <Input placeholder={t('easyPaperConfig.vlmModelPlaceholder')} autoComplete="off" />
            </Form.Item>
            <Form.Item name="vlmBaseUrl" label="Base URL" style={{ marginBottom: 10 }}>
              <Input placeholder={t('easyPaperConfig.baseUrlPlaceholder')} autoComplete="off" />
            </Form.Item>
            <Form.Item name="vlmApiKey" label="API Key" style={{ marginBottom: 10 }}>
              <Input.Password placeholder={t('easyPaperConfig.apiKeyPlaceholder')} autoComplete="off" />
            </Form.Item>
          </>
        ) : null}

        {showInlineSave ? (
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <Button type="primary" icon={<SaveOutlined />} onClick={onSave}>
              {t('easyPaperConfig.save')}
            </Button>
            <Text type="secondary" style={{ fontSize: 11, alignSelf: 'center' }}>
              {t('easyPaperConfig.saveHint')}
            </Text>
          </div>
        ) : null}
      </Form>
    </div>
  );
}
