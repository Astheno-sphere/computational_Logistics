/**
 * Map Placeholder Component
 * Displays agent positions without actual map (fallback when map library is not available)
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { useReplay } from '../store';

export const MapPlaceholder: React.FC = () => {
  const { t } = useTranslation();
  const { state, actions } = useReplay();
  const { agentProfiles, positionsAtStep, selectedAgentId } = state;

  // Get agents with positions
  const agentsWithPositions = React.useMemo(() => {
    return positionsAtStep
      .filter((position) => position.lng != null && position.lat != null)
      .map((position) => {
        const profile = agentProfiles.get(position.agent_id);
        return {
          id: position.agent_id,
          name: profile?.name || `Agent ${position.agent_id}`,
          lng: Number(position.lng),
          lat: Number(position.lat),
        };
      });
  }, [agentProfiles, positionsAtStep]);

  if (agentsWithPositions.length === 0) {
    return (
      <div className="map-placeholder">
        <div className="map-placeholder-icon">🗺️</div>
        <div>{t('replay.placeholder.noLocation')}</div>
        <div style={{ fontSize: '12px', marginTop: '8px' }}>
          {t('replay.placeholder.noLocationHint')}
        </div>
      </div>
    );
  }

  // Simple visualization: show agents as a list with coordinates
  return (
    <div style={{ padding: '16px', overflow: 'auto', height: '100%' }}>
      <div style={{ marginBottom: '16px', fontSize: '14px', fontWeight: 500 }}>
        {t('replay.placeholder.agentPositions', { count: agentsWithPositions.length })}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {agentsWithPositions.map((agent) => {
          const isSelected = agent.id === selectedAgentId;

          return (
            <div
              key={agent.id}
              onClick={() => actions.selectAgent(isSelected ? null : agent.id)}
              style={{
                padding: '12px',
                borderRadius: '8px',
                background: isSelected
                  ? 'var(--vscode-list-activeSelectionBackground)'
                  : 'var(--vscode-editor-inactiveSelectionBackground)',
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontWeight: 500 }}>{agent.name}</span>
                <span style={{ fontSize: '11px', opacity: 0.7 }}>ID: {agent.id}</span>
              </div>
              <div style={{ fontSize: '12px', opacity: 0.8 }}>
                📍 {agent.lng.toFixed(6)}, {agent.lat.toFixed(6)}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{
        marginTop: '24px',
        padding: '12px',
        background: 'var(--vscode-editor-inactiveSelectionBackground)',
        borderRadius: '8px',
        fontSize: '12px',
        lineHeight: 1.5,
      }}>
        <div style={{ fontWeight: 500, marginBottom: '8px' }}>{t('replay.placeholder.mapIntegration')}</div>
        <div style={{ opacity: 0.8 }}>
          {t('replay.placeholder.mapIntegrationHint')}
        </div>
        <code style={{
          display: 'block',
          marginTop: '8px',
          padding: '8px',
          background: 'var(--vscode-editor-background)',
          borderRadius: '4px',
          fontSize: '11px',
        }}>
          {t('replay.placeholder.installHint')}
        </code>
      </div>
    </div>
  );
};
