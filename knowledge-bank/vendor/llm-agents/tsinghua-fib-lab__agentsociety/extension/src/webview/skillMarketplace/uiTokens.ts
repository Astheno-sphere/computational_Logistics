import type { CSSProperties } from 'react';
import type { VscodeThemePalette } from '../theme';

/** Shared layout tokens for the skill management webview. */
export const SKILL_UI = {
  radius: {
    sm: 8,
    md: 12,
    lg: 16,
  },
  space: {
    xs: 6,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
  },
  maxWidth: 1180,
  cardMinWidth: 340,
} as const;

export function surfaceCardStyle(palette: VscodeThemePalette, opts?: {
  accent?: string;
  muted?: boolean;
}): CSSProperties {
  return {
    background: opts?.muted ? palette.surfaceMuted : palette.surfaceMuted,
    border: `1px solid ${palette.panelBorder}`,
    borderLeft: opts?.accent ? `3px solid ${opts.accent}` : undefined,
    borderRadius: SKILL_UI.radius.md,
    boxShadow: '0 1px 0 rgba(0,0,0,0.04)',
  };
}

export function sectionShellStyle(palette: VscodeThemePalette): CSSProperties {
  return {
    marginBottom: SKILL_UI.space.xl,
    padding: `${SKILL_UI.space.lg}px ${SKILL_UI.space.lg}px ${SKILL_UI.space.md}px`,
    borderRadius: SKILL_UI.radius.md,
    border: `1px solid ${palette.panelBorder}`,
    background: `linear-gradient(180deg, ${palette.surfaceBackground} 0%, ${palette.editorBackground} 100%)`,
  };
}

export function heroShellStyle(palette: VscodeThemePalette): CSSProperties {
  return {
    marginBottom: SKILL_UI.space.xl,
    padding: '22px 24px',
    borderRadius: SKILL_UI.radius.lg,
    border: `1px solid ${palette.panelBorder}`,
    background: `linear-gradient(180deg, ${palette.surfaceBackground} 0%, ${palette.editorBackground} 100%)`,
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
  };
}

export function iconBadgeStyle(accent: string): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 40,
    height: 40,
    borderRadius: SKILL_UI.radius.md,
    flexShrink: 0,
    background: `linear-gradient(145deg, ${accent}28 0%, ${accent}0c 100%)`,
    color: accent,
  };
}

export function skillGridStyle(): CSSProperties {
  return {
    display: 'grid',
    gridTemplateColumns: `repeat(auto-fill, minmax(${SKILL_UI.cardMinWidth}px, 1fr))`,
    gap: SKILL_UI.space.md,
  };
}
