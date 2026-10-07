import type { CSSProperties } from 'react';
import type { VscodeThemePalette } from '../theme';

export function glassCardStyle(isDark: boolean, palette: VscodeThemePalette): CSSProperties {
  return {
    marginBottom: 16,
    borderRadius: 12,
    border: `1px solid ${palette.panelBorder}`,
    background: isDark ? 'rgba(37, 37, 38, 0.6)' : 'rgba(255, 255, 255, 0.5)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    boxShadow: '0 2px 10px rgba(0,0,0,0.06)',
  };
}

export function advancedPanelInnerStyle(isDark: boolean, palette: VscodeThemePalette): CSSProperties {
  return {
    padding: '16px 18px 8px',
    borderRadius: 10,
    background: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
    border: `1px solid ${palette.panelBorder}`,
  };
}

export const tabBodyStyle: CSSProperties = {
  paddingTop: 4,
  paddingBottom: 4,
};
