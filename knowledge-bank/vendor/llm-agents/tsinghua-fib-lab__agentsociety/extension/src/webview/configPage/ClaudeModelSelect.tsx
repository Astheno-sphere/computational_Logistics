import * as React from 'react';
import { Select } from 'antd';
import type { ClaudeModelOption } from './claudeCodeTypes';

export interface ClaudeModelSelectProps {
  value?: string;
  onChange?: (value: string) => void;
  models: ClaudeModelOption[];
  placeholder: string;
  disabled?: boolean;
  loading?: boolean;
}

export const ClaudeModelSelect: React.FC<ClaudeModelSelectProps> = ({
  value,
  onChange,
  models,
  placeholder,
  disabled,
  loading,
}) => {
  const options = React.useMemo(
    () =>
      models.map((m) => ({
        value: m.id,
        label: m.label ? `${m.label} (${m.id})` : m.id,
      })),
    [models]
  );

  return (
    <Select
      showSearch
      allowClear
      placeholder={placeholder}
      value={value?.trim() ? value : undefined}
      onChange={(next) => onChange?.(next ?? '')}
      disabled={disabled}
      loading={loading}
      options={options}
      optionFilterProp="label"
      style={{ width: '100%' }}
      popupMatchSelectWidth
      listHeight={320}
      notFoundContent={placeholder}
    />
  );
};
