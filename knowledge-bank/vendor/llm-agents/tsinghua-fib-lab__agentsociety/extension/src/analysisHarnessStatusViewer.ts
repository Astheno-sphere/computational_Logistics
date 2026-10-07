/**
 * Analysis harness phase status viewer (hypothesis + synthesis).
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as yaml from 'js-yaml';
import { localize, isExtensionZh } from './i18n';

const HYPOTHESIS_PHASES = ['frame', 'explore', 'claims', 'refine', 'produce'] as const;

const PHASE_LABEL_KEYS: Record<(typeof HYPOTHESIS_PHASES)[number], string> = {
  frame: 'projectStructure.analysisPhase.frame',
  explore: 'projectStructure.analysisPhase.explore',
  claims: 'projectStructure.analysisPhase.claims',
  refine: 'projectStructure.analysisPhase.refine',
  produce: 'projectStructure.analysisPhase.produce',
};

export type AnalysisHarnessViewArgs = {
  statePath: string;
  scope: 'hypothesis' | 'synthesis';
  focusPhase?: string;
};

type PhaseCheckpoint = {
  structural_pass?: boolean;
  attestation_pass?: boolean;
  gate_pass?: boolean;
  completed_at?: string;
};

type ValidationRecord = {
  phase?: string;
  status?: string;
  at?: string;
};

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatChartCountLabel(
  chartCount: unknown,
  maxCharts: unknown,
  isZh: boolean
): string {
  const count = Number(chartCount) || 0;
  const cap = Number(maxCharts) || 0;
  if (cap > 0) {
    return `${count} / ${cap}`;
  }
  return isZh ? `${count}（无上限，按主张需要作图）` : `${count} (no cap; charts per claim)`;
}

function readState(statePath: string): Record<string, unknown> | undefined {
  try {
    const raw = yaml.load(fs.readFileSync(statePath, 'utf8'));
    return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : undefined;
  } catch {
    return undefined;
  }
}

function phaseIndex(phase: string): number {
  return HYPOTHESIS_PHASES.indexOf(phase as (typeof HYPOTHESIS_PHASES)[number]);
}

function resolveStepStatus(
  phase: string,
  currentPhase: string,
  checkpoint: PhaseCheckpoint
): 'pass' | 'current' | 'attestation' | 'blocked' | 'pending' {
  if (checkpoint.gate_pass) {
    return 'pass';
  }
  const cur = phaseIndex(currentPhase);
  const idx = phaseIndex(phase);
  if (phase === currentPhase) {
    if (checkpoint.structural_pass && !checkpoint.attestation_pass) {
      return 'attestation';
    }
    return 'current';
  }
  if (idx >= 0 && cur >= 0 && idx < cur) {
    return 'blocked';
  }
  return 'pending';
}

function statusLabel(kind: ReturnType<typeof resolveStepStatus>): string {
  switch (kind) {
    case 'pass':
      return localize('projectStructure.phaseStatus.pass');
    case 'current':
      return localize('projectStructure.phaseStatus.current');
    case 'attestation':
      return localize('projectStructure.phaseStatus.attestationPending');
    case 'blocked':
      return localize('projectStructure.phaseStatus.blocked');
    default:
      return localize('projectStructure.phaseStatus.pending');
  }
}

export class AnalysisHarnessStatusViewer {
  private static currentPanel: vscode.WebviewPanel | undefined;

  public static async show(args: AnalysisHarnessViewArgs): Promise<void> {
    const { statePath, scope, focusPhase } = args;
    if (!statePath || !fs.existsSync(statePath)) {
      vscode.window.showErrorMessage(localize('extension.viewAnalysisHarness.missingState'));
      return;
    }

    const state = readState(statePath);
    if (!state) {
      vscode.window.showErrorMessage(localize('extension.viewAnalysisHarness.parseError'));
      return;
    }

    const isZh = isExtensionZh();
    const title =
      scope === 'synthesis'
        ? localize('extension.viewAnalysisHarness.titleSynthesis')
        : localize('extension.viewAnalysisHarness.titleHypothesis', String(state.hypothesis_id || '?'));

    if (this.currentPanel) {
      this.currentPanel.title = title;
      this.currentPanel.reveal(vscode.ViewColumn.One);
      this.currentPanel.webview.html = this.buildHtml(state, statePath, scope, focusPhase, isZh);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      'analysisHarnessStatusViewer',
      title,
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    this.currentPanel = panel;
    panel.webview.onDidReceiveMessage((msg: { command?: string; path?: string }) => {
      if (msg.command === 'openStateYaml' && msg.path && fs.existsSync(msg.path)) {
        void vscode.window.showTextDocument(vscode.Uri.file(msg.path));
      }
    });
    panel.onDidDispose(() => {
      this.currentPanel = undefined;
    });
    panel.webview.html = this.buildHtml(state, statePath, scope, focusPhase, isZh);
  }

  private static buildHtml(
    state: Record<string, unknown>,
    statePath: string,
    scope: 'hypothesis' | 'synthesis',
    focusPhase: string | undefined,
    isZh: boolean
  ): string {
    const labels = {
      title: isZh ? '分析 Harness 状态' : 'Analysis harness status',
      currentPhase: isZh ? '当前阶段' : 'Current phase',
      release: isZh ? '发布状态' : 'Release',
      structural: isZh ? '结构校验' : 'Structural',
      attestation: isZh ? '阶段签署' : 'Attestation',
      gate: isZh ? '门禁' : 'Gate',
      pass: isZh ? '通过' : 'Pass',
      fail: isZh ? '未通过' : 'Fail',
      pending: isZh ? '待完成' : 'Pending',
      scope: isZh ? '综合范围' : 'Synthesis scope',
      chartCount: isZh ? '图表数' : 'Charts',
      lastValidation: isZh ? '最近校验' : 'Last validation',
      openYaml: isZh ? '在编辑器打开 state.yaml' : 'Open state.yaml in editor',
      noAttestation: isZh ? '尚未 record-attestation' : 'No record-attestation yet',
      findings: isZh ? '关键发现' : 'Key findings',
      nextStep: isZh ? '建议下一步' : 'Recommended next',
      updated: isZh ? '更新时间' : 'Updated',
    };

    const checkpoints = (state.phase_checkpoints || {}) as Record<string, PhaseCheckpoint>;
    const attestations = (state.phase_attestations || {}) as Record<string, Record<string, unknown>>;
    const history = (Array.isArray(state.validation_history) ? state.validation_history : []) as ValidationRecord[];
    const currentPhase = String(state.current_phase || (scope === 'synthesis' ? 'synthesis' : 'frame'));
    const focus = focusPhase || currentPhase;

    let body = '';

    if (scope === 'synthesis') {
      const release = String(state.workspace_release || 'not_started');
      const scopeIds = (state.synthesis_scope_hypothesis_ids as string[]) || [];
      const att = state.phase_attestation as Record<string, unknown> | undefined;
      const lastSynth = [...history].reverse().find((h) => h.phase === 'synthesis');
      body += `
        <section class="summary">
          <div class="meta-row"><span class="label">${labels.release}</span><span class="badge ${release === 'ready' ? 'ok' : 'warn'}">${escapeHtml(release)}</span></div>
          ${scopeIds.length ? `<div class="meta-row"><span class="label">${labels.scope}</span><span>${escapeHtml(scopeIds.join(', '))}</span></div>` : ''}
          ${lastSynth ? `<div class="meta-row"><span class="label">${labels.lastValidation}</span><span>${escapeHtml(lastSynth.status || '')} · ${escapeHtml(String(lastSynth.at || ''))}</span></div>` : ''}
        </section>`;
      if (att) {
        const findings = (att.key_findings as string[]) || [];
        body += `<section class="detail focus"><h3>${localize('projectStructure.analysisPhase.synthesis')}</h3>`;
        if (findings.length) {
          body += `<ul>${findings.map((f) => `<li>${escapeHtml(f)}</li>`).join('')}</ul>`;
        } else {
          body += `<p class="muted">${labels.noAttestation}</p>`;
        }
        if (att.recommended_next_step) {
          body += `<p class="hint"><strong>${labels.nextStep}:</strong> ${escapeHtml(String(att.recommended_next_step))}</p>`;
        }
        body += '</section>';
      }
    } else {
      const release = String(state.hypothesis_release || 'not_started');
      const passed = HYPOTHESIS_PHASES.filter((p) => checkpoints[p]?.gate_pass).length;
      body += `
        <section class="summary">
          <div class="meta-row"><span class="label">${labels.currentPhase}</span><span class="badge accent">${escapeHtml(localize(PHASE_LABEL_KEYS[currentPhase as keyof typeof PHASE_LABEL_KEYS] || currentPhase))}</span></div>
          <div class="meta-row"><span class="label">${labels.release}</span><span class="badge ${release === 'ready' ? 'ok' : 'warn'}">${escapeHtml(release)}</span></div>
          <div class="meta-row"><span class="label">${isZh ? '阶段进度' : 'Progress'}</span><span>${passed} / ${HYPOTHESIS_PHASES.length} ${labels.pass}</span></div>
          ${state.chart_count !== null && state.chart_count !== undefined
          ? `<div class="meta-row"><span class="label">${labels.chartCount}</span><span>${escapeHtml(
            formatChartCountLabel(state.chart_count, state.max_charts, isZh)
          )}</span></div>`
          : ''
        }
          ${state.updated_at ? `<div class="meta-row"><span class="label">${labels.updated}</span><span>${escapeHtml(String(state.updated_at))}</span></div>` : ''}
        </section>
        <section class="timeline">`;

      for (const phase of HYPOTHESIS_PHASES) {
        const cp = checkpoints[phase] || {};
        const kind = resolveStepStatus(phase, currentPhase, cp);
        const isFocus = phase === focus;
        const att = attestations[phase];
        const lastVal = [...history].reverse().find((h) => h.phase === phase);
        const phaseLabel = localize(PHASE_LABEL_KEYS[phase]);

        body += `
          <article class="phase-card ${kind} ${isFocus ? 'focus' : ''}" id="phase-${phase}">
            <header>
              <h3>${escapeHtml(phaseLabel)}</h3>
              <span class="status-pill ${kind}">${escapeHtml(statusLabel(kind))}</span>
            </header>
            <div class="checks">
              <span class="check ${cp.structural_pass ? 'ok' : 'no'}">${labels.structural}: ${cp.structural_pass ? labels.pass : labels.fail}</span>
              <span class="check ${cp.attestation_pass ? 'ok' : 'no'}">${labels.attestation}: ${cp.attestation_pass ? labels.pass : labels.fail}</span>
              <span class="check ${cp.gate_pass ? 'ok' : 'no'}">${labels.gate}: ${cp.gate_pass ? labels.pass : labels.fail}</span>
            </div>
            ${lastVal ? `<p class="muted">${labels.lastValidation}: ${escapeHtml(lastVal.status || '')} · ${escapeHtml(String(lastVal.at || ''))}</p>` : ''}
            ${att && Array.isArray(att.key_findings) && (att.key_findings as string[]).length
            ? `<div class="findings"><strong>${labels.findings}</strong><ul>${(att.key_findings as string[])
              .slice(0, 5)
              .map((f) => `<li>${escapeHtml(f)}</li>`)
              .join('')}</ul></div>`
            : kind === 'attestation' || kind === 'current'
              ? `<p class="hint">${labels.noAttestation}</p>`
              : ''}
            ${att?.recommended_next_step ? `<p class="hint"><strong>${labels.nextStep}:</strong> ${escapeHtml(String(att.recommended_next_step))}</p>` : ''}
          </article>`;
      }
      body += '</section>';
    }

    const safePath = escapeHtml(statePath);
    const focusScript = focus
      ? `document.getElementById('phase-${focus}')?.scrollIntoView({ block: 'nearest' });`
      : '';

    return `<!DOCTYPE html>
<html lang="${isZh ? 'zh-CN' : 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${labels.title}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: var(--vscode-font-family);
      background: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      padding: 16px 20px 32px;
      line-height: 1.5;
    }
    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    .toolbar h1 { font-size: 18px; font-weight: 600; }
    .btn {
      padding: 6px 12px;
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    .btn:hover { background: var(--vscode-button-secondaryHoverBackground); }
    .path { font-size: 11px; color: var(--vscode-descriptionForeground); margin-bottom: 16px; word-break: break-all; }
    .summary { margin-bottom: 20px; }
    .meta-row { display: flex; gap: 12px; margin: 6px 0; font-size: 13px; }
    .meta-row .label { min-width: 88px; color: var(--vscode-descriptionForeground); }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      background: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
    }
    .badge.ok { background: rgba(40, 167, 69, 0.2); color: #3dd68c; }
    .badge.warn { background: rgba(255, 193, 7, 0.15); color: #e5c07b; }
    .badge.accent { background: rgba(0, 122, 204, 0.2); color: #4fc3f7; }
    .timeline { display: flex; flex-direction: column; gap: 12px; }
    .phase-card {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 12px 14px;
      background: var(--vscode-sideBar-background);
    }
    .phase-card.focus {
      border-color: var(--vscode-focusBorder);
      box-shadow: 0 0 0 1px var(--vscode-focusBorder);
    }
    .phase-card.pass { border-left: 3px solid #3dd68c; }
    .phase-card.current, .phase-card.attestation { border-left: 3px solid #e5c07b; }
    .phase-card.blocked { border-left: 3px solid #f48771; }
    .phase-card header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .phase-card h3 { font-size: 14px; }
    .status-pill {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      background: var(--vscode-input-background);
    }
    .status-pill.pass { color: #3dd68c; }
    .status-pill.current, .status-pill.attestation { color: #e5c07b; }
    .status-pill.blocked { color: #f48771; }
    .checks { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; margin-bottom: 6px; }
    .check.ok { color: #3dd68c; }
    .check.no { color: var(--vscode-descriptionForeground); }
    .muted { font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 4px; }
    .hint { font-size: 12px; margin-top: 8px; color: var(--vscode-textLink-foreground); }
    .findings ul { margin: 4px 0 0 18px; font-size: 12px; }
    .detail { border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 12px; }
  </style>
</head>
<body>
  <div class="toolbar">
    <h1>${labels.title}</h1>
    <button class="btn" id="openYaml">${labels.openYaml}</button>
  </div>
  <div class="path">${safePath}</div>
  ${body}
  <script>
    const vscodeApi = acquireVsCodeApi();
    document.getElementById('openYaml').addEventListener('click', () => {
      vscodeApi.postMessage({ command: 'openStateYaml', path: ${JSON.stringify(statePath)} });
    });
    ${focusScript}
  </script>
</body>
</html>`;
  }
}
