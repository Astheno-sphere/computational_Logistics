import * as React from 'react';
import { Button, Tooltip, Typography } from 'antd';
import { CheckCircleOutlined } from '@ant-design/icons';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import type { ValidationState } from './types';

const { Text } = Typography;

export interface ValidationActionProps {
  t: TFunction;
  palette: VscodeThemePalette;
  state: ValidationState;
  disabledReason: string | null;
  onValidate: () => void;
  label?: string;
  size?: 'small' | 'middle' | 'large';
  primary?: boolean;
}

export const ValidationAction: React.FC<ValidationActionProps> = ({
  t,
  palette,
  state,
  disabledReason,
  onValidate,
  label = t('configPage.validate'),
  size = 'middle',
  primary = true,
}) => {
  const buttonType = primary ? 'primary' : 'default';

  if (state.validating) {
    return (
      <Button size={size} type={buttonType} loading disabled style={{ marginTop: 4 }}>
        {t('configPage.validating')}
      </Button>
    );
  }

  if (state.valid === true) {
    return (
      <Button
        size={size}
        icon={<CheckCircleOutlined />}
        onClick={onValidate}
        style={{
          marginTop: 4,
          color: palette.successForeground,
          borderColor: palette.successForeground,
          background: `${palette.successForeground}14`,
        }}
      >
        ✓ {t('configPage.validationSuccess')}
      </Button>
    );
  }

  if (state.valid === false && state.error) {
    return (
      <div style={{ marginTop: 4 }}>
        <Text type="danger" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          {state.error}
        </Text>
        <Button size={size} type={buttonType} icon={<CheckCircleOutlined />} onClick={onValidate}>
          {t('configPage.revalidate')}
        </Button>
      </div>
    );
  }

  if (disabledReason) {
    return (
      <div style={{ marginTop: 4 }}>
        <Text style={{ fontSize: 12, display: 'block', marginBottom: 8, color: palette.warningForeground }}>
          {disabledReason}
        </Text>
        <Tooltip title={disabledReason}>
          <Button
            size={size}
            type={buttonType}
            icon={<CheckCircleOutlined />}
            disabled
          >
            {label}
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <Tooltip title="">
      <Button
        size={size}
        type={buttonType}
        icon={<CheckCircleOutlined />}
        onClick={onValidate}
        style={{ marginTop: 4 }}
      >
        {label}
      </Button>
    </Tooltip>
  );
};
