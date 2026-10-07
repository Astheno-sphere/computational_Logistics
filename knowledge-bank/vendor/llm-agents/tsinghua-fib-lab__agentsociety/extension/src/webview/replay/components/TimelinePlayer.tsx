/**
 * Timeline Player Component
 * Controls for timeline navigation and playback
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Flex, Select, Slider, Space, Tooltip } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, FastForwardOutlined, FastBackwardOutlined, ReloadOutlined } from '@ant-design/icons';
import { useReplay } from '../store';
import dayjs from 'dayjs';

// Flickering dot component (simulating V1's FlickeringDot)
const FlickeringDot: React.FC<{ active?: boolean }> = ({ active }) => {
  return (
    <span
      className={`flickering-dot ${active ? 'active' : ''}`}
      style={{
        display: 'inline-block',
        width: '10px',
        height: '10px',
        borderRadius: '50%',
        backgroundColor: active
          ? 'var(--vscode-testing-iconPassed, #52c41a)'
          : 'var(--vscode-panel-border, #d9d9d9)',
        animation: active ? 'flicker 1s infinite' : 'none',
      }}
    />
  );
};

export const TimelinePlayer: React.FC = () => {
  const { t } = useTranslation();
  const { state, actions } = useReplay();
  const { timeline, currentStep, playback, experimentInfo } = state;

  const currentTimelinePoint = timeline[currentStep];
  const currentTime = currentTimelinePoint ? dayjs(currentTimelinePoint.t) : null;
  const currentStepNumber = currentTimelinePoint?.step ?? 0;

  const handleSliderChange = (value: number) => {
    actions.setCurrentStep(value);
  };

  const handleSpeedChange = (value: number) => {
    actions.setPlaybackSpeed(value);
  };

  const togglePlay = () => {
    if (playback.isPlaying) {
      actions.pause();
    } else {
      // If at the end, restart from beginning
      if (currentStep >= timeline.length - 1) {
        actions.setCurrentStep(0);
      }
      actions.play();
    }
  };

  const totalSteps = experimentInfo?.total_steps ?? timeline.length;

  // Slider tooltip formatter like V1
  const sliderFormatter = (value: number | undefined) => {
    if (value === undefined || timeline[value] === undefined) {
      return '';
    }
    const point = timeline[value];
    return t('replay.timeline.stepTooltip', { step: point.step, time: dayjs(point.t).format('HH:mm:ss') });
  };

  // Speed options like V1
  const speedOptions = [
    { value: 2000, label: '0.5x' },
    { value: 1000, label: '1x' },
    { value: 500, label: '2x' },
    { value: 250, label: '4x' },
    { value: 100, label: '10x' },
  ];

  return (
    <Flex align="center" gap="small" className="timeline-player">
      {/* Status indicator */}
      <Flex className="status" align="center">
        <Tooltip title={t('replay.timeline.status')}>
          <Space style={{ paddingLeft: '4px' }}>
            <FlickeringDot active={timeline.length > 0} />
            <Button
              shape="circle"
              type="text"
              icon={<ReloadOutlined />}
              size="small"
              title={t('replay.timeline.refresh')}
            />
          </Space>
        </Tooltip>
      </Flex>

      {/* Player controls - width fits content like status bar, no extra space on right */}
      <Flex align="center" className="player" style={{ flex: '0 0 auto', width: 'fit-content', maxWidth: 'fit-content' }}>
        <Button
          shape="circle"
          size="small"
          type="text"
          onClick={actions.prevStep}
          disabled={currentStep === 0 || playback.isPlaying}
          icon={<FastBackwardOutlined />}
        />
        <Button
          shape="circle"
          type="text"
          onClick={togglePlay}
          disabled={timeline.length === 0}
          icon={playback.isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
        />
        <Button
          shape="circle"
          size="small"
          type="text"
          onClick={actions.nextStep}
          disabled={currentStep === timeline.length - 1 || playback.isPlaying}
          icon={<FastForwardOutlined />}
        />
      </Flex>

      {/* Slider - take remaining width (avoid idle space to the right of fast-forward) */}
      <Flex className="timeline-slider-wrap" style={{ flex: 1, minWidth: 0 }}>
        <Slider
          min={0}
          max={Math.max(0, timeline.length - 1)}
          value={currentStep}
          onChange={handleSliderChange}
          disabled={playback.isPlaying || timeline.length === 0}
          tooltip={{ formatter: sliderFormatter }}
          style={{ width: '100%' }}
        />
      </Flex>

      {/* Current time display */}
      <Flex>
        <Flex vertical align="center">
          <strong>{t('replay.timeline.step', { current: currentStepNumber, total: totalSteps })}</strong>
          <span style={{ fontSize: '11px', color: 'var(--vscode-descriptionForeground)' }}>
            {currentTime ? currentTime.format('HH:mm:ss') : '--:--:--'}
          </span>
        </Flex>
      </Flex>

      {/* Speed selector */}
      <Flex className="circle-wrap">
        <Select
          value={playback.speed}
          onChange={handleSpeedChange}
          placement="topLeft"
          style={{ width: '80px' }}
          options={speedOptions}
        />
      </Flex>
    </Flex>
  );
};
