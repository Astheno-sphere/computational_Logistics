import * as React from 'react';
import { Button, Form, Input, Radio, Space, Tag, Typography } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { TFunction } from 'i18next';
import type { ConfigValues } from './types';

const { Text } = Typography;

export type PythonEnvironmentOption = {
  path: string;
  source: string;
  compatible: boolean;
  pythonVersion?: string;
  as2Version?: string;
  error?: string;
};

type Props = {
  t: TFunction;
  form: FormInstance<ConfigValues>;
  options: PythonEnvironmentOption[];
  scanning: boolean;
  onScan: () => void;
};

export function PythonEnvironmentPicker({
  t,
  form,
  options,
  scanning,
  onScan,
}: Props) {
  const currentPath = Form.useWatch('pythonPath', form) ?? '';

  const applyPath = (nextPath: string) => {
    form.setFieldValue('pythonPath', nextPath);
  };

  React.useEffect(() => {
    if (currentPath.trim()) {
      return;
    }
    const compatible = options.filter((item) => item.compatible);
    if (compatible.length === 1) {
      form.setFieldValue('pythonPath', compatible[0].path);
    }
  }, [currentPath, form, options]);

  const sourceLabel = (source: string) =>
    t(`configPage.python.sources.${source}`, { defaultValue: source });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {t('configPage.python.scanHint')}
        </Text>
        <Button
          size="small"
          icon={<ReloadOutlined />}
          loading={scanning}
          onClick={onScan}
        >
          {t('configPage.python.scan')}
        </Button>
      </Space>

      {options.length > 0 ? (
        <Radio.Group
          value={currentPath || undefined}
          onChange={(event) => applyPath(String(event.target.value))}
          style={{ width: '100%' }}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            {options.map((item) => (
              <Radio key={item.path} value={item.path} style={{ alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                  <Space size={6} wrap>
                    {item.compatible ? (
                      <Tag icon={<CheckCircleOutlined />} color="success" style={{ margin: 0 }}>
                        {t('configPage.python.compatible')}
                      </Tag>
                    ) : (
                      <Tag icon={<CloseCircleOutlined />} color="default" style={{ margin: 0 }}>
                        {t('configPage.python.incompatible')}
                      </Tag>
                    )}
                    <Tag style={{ margin: 0 }}>{sourceLabel(item.source)}</Tag>
                    {item.pythonVersion ? (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        Python {item.pythonVersion}
                      </Text>
                    ) : null}
                    {item.as2Version ? (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        agentsociety2 {item.as2Version}
                      </Text>
                    ) : null}
                  </Space>
                  <Text code style={{ fontSize: 11, wordBreak: 'break-all' }}>
                    {item.path}
                  </Text>
                </div>
              </Radio>
            ))}
          </Space>
        </Radio.Group>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {scanning ? t('configPage.python.scanning') : t('configPage.python.scanEmpty')}
        </Text>
      )}

      <Form.Item
        name="pythonPath"
        label={t('configPage.python.pathManual')}
        style={{ marginBottom: 0 }}
      >
        <Input placeholder={t('configPage.python.pathPlaceholder')} />
      </Form.Item>
    </div>
  );
}
