import * as React from 'react';
import { Card, Segmented, Space, Spin, Tag, Typography } from 'antd';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import { GatewayUsageChart } from './GatewayUsageChart';
import type { TokenUsageRecord } from './gatewayUsageTypes';
import {
  buildUsageChartSeries,
  formatTokenCount,
  hasGatewayUsageData,
  resolveGatewayUsageView,
  type UsageRangeFilter,
  type UsageTrendMetric,
} from './gatewayUsageView';

const { Text } = Typography;

type Props = {
  t: TFunction;
  palette: VscodeThemePalette;
  background?: string;
  records: TokenUsageRecord[];
  loading?: boolean;
  range?: UsageRangeFilter;
  title: string;
  subtitle?: string;
  height?: number;
  showMetricToggle?: boolean;
};

export function GatewayUsageTrendCard({
  t,
  palette,
  background,
  records,
  loading = false,
  range = '7d',
  title,
  subtitle,
  height = 210,
  showMetricToggle = true,
}: Props) {
  const [trendMetric, setTrendMetric] = React.useState<UsageTrendMetric>('tokens');
  const viewAggregation = React.useMemo(
    () => resolveGatewayUsageView(records, { range, app: 'all' }),
    [records, range]
  );
  const chart = React.useMemo(() => {
    if (!viewAggregation) {
      return { labels: [] as string[], series: [] };
    }
    return buildUsageChartSeries(viewAggregation, trendMetric, t, palette);
  }, [palette, t, trendMetric, viewAggregation]);
  const hasData = hasGatewayUsageData(viewAggregation);
  const hasTrend = chart.labels.length >= 2;

  return (
    <Card
      size="small"
      style={{
        borderRadius: 12,
        border: `1px solid ${palette.panelBorder}`,
        background,
      }}
      styles={{ body: { padding: '12px 14px 10px' } }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 10,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <Text strong style={{ fontSize: 13 }}>
            {title}
          </Text>
          {subtitle ? (
            <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
              {subtitle}
            </Text>
          ) : null}
        </div>
        {viewAggregation ? (
          <Space size={6} wrap>
            <Tag style={{ margin: 0 }}>
              {t('configPage.metrics.requests', { count: viewAggregation.totalRequests })}
            </Tag>
            <Tag style={{ margin: 0 }}>
              {t('claudeCodeConfig.usageColInput')} {formatTokenCount(viewAggregation.totalInputTokens)}
            </Tag>
            <Tag style={{ margin: 0 }}>
              {t('claudeCodeConfig.usageColOutput')} {formatTokenCount(viewAggregation.totalOutputTokens)}
            </Tag>
          </Space>
        ) : null}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '28px 0' }}>
          <Spin size="small" />
        </div>
      ) : (
        <>
          {showMetricToggle && hasTrend ? (
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginBottom: 8,
              }}
            >
              <Segmented
                size="small"
                value={trendMetric}
                onChange={(value) => setTrendMetric(value as UsageTrendMetric)}
                options={[
                  { label: t('claudeCodeConfig.usageChartRequests'), value: 'requests' },
                  { label: t('claudeCodeConfig.usageChartTokens'), value: 'tokens' },
                ]}
              />
            </div>
          ) : null}
          {hasTrend ? (
            <GatewayUsageChart
              title={title}
              labels={chart.labels}
              series={chart.series}
              palette={palette}
              height={height}
              valueFormatter={(value) =>
                trendMetric === 'requests'
                  ? String(Math.round(value))
                  : formatTokenCount(value)
              }
            />
          ) : null}
          {!hasData ? (
            <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>
              {t('configPage.dashboard.claudeUsageEmpty')}
            </Text>
          ) : !hasTrend ? (
            <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>
              {t('claudeCodeConfig.usageTrendNeedMore')}
            </Text>
          ) : null}
        </>
      )}
    </Card>
  );
}
