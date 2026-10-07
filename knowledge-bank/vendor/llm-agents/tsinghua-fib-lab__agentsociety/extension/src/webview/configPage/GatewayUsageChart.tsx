import * as React from 'react';
import { Space, Typography } from 'antd';
import type { VscodeThemePalette } from '../theme';

const { Text } = Typography;

export type ChartSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
};

export interface GatewayUsageChartProps {
  title: string;
  labels: string[];
  series: ChartSeries[];
  palette: VscodeThemePalette;
  height?: number;
  valueFormatter?: (n: number) => string;
}

function smoothPath(points: Array<{ x: number; y: number }>): string {
  if (points.length === 0) {
    return '';
  }
  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }
  return points.slice(1).reduce((path, point, index) => {
    const previous = points[index];
    const midX = (previous.x + point.x) / 2;
    return `${path} C ${midX} ${previous.y}, ${midX} ${point.y}, ${point.x} ${point.y}`;
  }, `M ${points[0].x} ${points[0].y}`);
}

function niceMax(max: number): number {
  if (max <= 0) {
    return 1;
  }
  const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
  const normalized = max / magnitude;
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return nice * magnitude;
}

/**
 * Pure SVG bar chart with hover-driven crosshair + tooltip.
 *
 * On mouse move the container finds the nearest bucket and shows a vertical
 * line plus a tooltip card listing every series value at that bucket.  This is
 * much easier to use than hunting for tiny circle datapoints.
 */
export function GatewayUsageChart({
  title,
  labels,
  series,
  palette,
  height = 220,
  valueFormatter = (n) => String(Math.round(n)),
}: GatewayUsageChartProps) {
  const chartId = React.useId().replace(/:/g, '');
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [hoverIndex, setHoverIndex] = React.useState<number | null>(null);
  const width = 760;
  const padL = 56;
  const padR = 18;
  const padT = 18;
  const padB = 42;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const bucketCount = Math.max(labels.length, 1);
  const xStep = bucketCount > 1 ? innerW / (bucketCount - 1) : 0;
  const seriesMax = Math.max(...series.flatMap((item) => item.values), 0);
  const ymax = niceMax(seriesMax);
  const yTicks = [0, 0.25, 0.5, 0.75, 1];
  const labelStep = bucketCount <= 8 ? 1 : Math.ceil(bucketCount / 8);

  const handleMouseMove = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || bucketCount === 0) return;
      const ratX = (e.clientX - rect.left) / rect.width;
      const svgX = ratX * width;
      const idx = Math.round((svgX - padL) / xStep);
      if (idx < 0 || idx >= bucketCount) {
        setHoverIndex(null);
        return;
      }
      setHoverIndex(idx);
    },
    [bucketCount, xStep],
  );

  const handleMouseLeave = React.useCallback(() => setHoverIndex(null), []);

  const lineX =
    hoverIndex !== null && bucketCount > 1
      ? padL + xStep * hoverIndex
      : null;

  return (
    <div>
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          background: palette.codeBlockBackground,
          borderRadius: 8,
          padding: '10px 12px 8px',
          border: `1px solid ${palette.panelBorder}`,
          cursor: 'crosshair',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          style={{ display: 'block', minHeight: 190, maxHeight: height }}
          role="img"
          aria-label={title}
        >
          {yTicks.map((tick) => {
            const y = padT + innerH * (1 - tick);
            return (
              <g key={tick}>
                <line
                  x1={padL}
                  y1={y}
                  x2={width - padR}
                  y2={y}
                  stroke={palette.panelBorder}
                  strokeDasharray={tick === 0 ? undefined : '4 5'}
                />
                <text
                  x={padL - 9}
                  y={y + 4}
                  textAnchor="end"
                  fontSize={11}
                  fill={palette.descriptionForeground}
                >
                  {valueFormatter(ymax * tick)}
                </text>
              </g>
            );
          })}
          {labels.map((label, bucketIndex) => {
            const centerX = bucketCount > 1 ? padL + xStep * bucketIndex : padL + innerW / 2;
            return (
              <g key={`${label}-${bucketIndex}`}>
                {bucketIndex % labelStep === 0 || bucketIndex === labels.length - 1 ? (
                  <text
                    x={centerX}
                    y={height - 14}
                    textAnchor="middle"
                    fontSize={11}
                    fill={palette.descriptionForeground}
                  >
                    {label}
                  </text>
                ) : null}
              </g>
            );
          })}
          {series.map((item) => {
            const points = labels.map((_, index) => ({
              x: bucketCount > 1 ? padL + xStep * index : padL + innerW / 2,
              y: padT + innerH * (1 - (item.values[index] ?? 0) / ymax),
            }));
            const path = smoothPath(points);
            const areaPath =
              points.length > 1
                ? `${path} L ${points[points.length - 1].x} ${padT + innerH} L ${points[0].x} ${padT + innerH} Z`
                : '';
            return (
              <g key={item.id}>
                <defs>
                  <linearGradient id={`${chartId}-${item.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={item.color} stopOpacity="0.16" />
                    <stop offset="100%" stopColor={item.color} stopOpacity="0" />
                  </linearGradient>
                </defs>
                {areaPath ? <path d={areaPath} fill={`url(#${chartId}-${item.id})`} /> : null}
                <path
                  d={path}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={2.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {points.map((point, index) => (
                  <circle
                    key={`${item.id}-${index}`}
                    cx={point.x}
                    cy={point.y}
                    r={labels.length <= 12 ? 3 : 2}
                    fill={item.color}
                    stroke={palette.codeBlockBackground}
                    strokeWidth={1.5}
                  />
                ))}
              </g>
            );
          })}
          {/* Crosshair */}
          {lineX !== null ? (
            <line
              x1={lineX}
              x2={lineX}
              y1={padT}
              y2={padT + innerH}
              stroke={palette.editorForeground}
              strokeWidth={1}
              strokeDasharray="4 3"
              opacity={0.55}
            />
          ) : null}
        </svg>

        {/* Tooltip card */}
        {hoverIndex !== null ? (
          <div
            style={{
              position: 'absolute',
              top: 8,
              left: lineX !== null ? `${((lineX - padL) / innerW) * 100}%` : '50%',
              transform: 'translateX(-50%)',
              background: palette.editorBackground,
              border: `1px solid ${palette.panelBorder}`,
              borderRadius: 6,
              padding: '6px 10px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              pointerEvents: 'none',
              zIndex: 2,
              whiteSpace: 'nowrap',
            }}
          >
            <Text strong style={{ fontSize: 11, display: 'block', marginBottom: 3 }}>
              {labels[hoverIndex]}
            </Text>
            {series.map((item) => (
              <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 1 }}>
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: 2,
                    background: item.color,
                    display: 'inline-block',
                    flexShrink: 0,
                  }}
                />
                <Text type="secondary" style={{ fontSize: 10 }}>
                  {item.label}: {valueFormatter(item.values[hoverIndex] ?? 0)}
                </Text>
              </div>
            ))}
          </div>
        ) : null}

        <Space size={[14, 4]} wrap style={{ marginTop: 4 }}>
          {series.map((item) => (
            <Space key={item.id} size={5}>
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: 2,
                  background: item.color,
                  display: 'inline-block',
                }}
              />
              <Text type="secondary" style={{ fontSize: 11 }}>
                {item.label} · {valueFormatter(item.values.reduce((sum, value) => sum + value, 0))}
              </Text>
            </Space>
          ))}
        </Space>
      </div>
    </div>
  );
}
