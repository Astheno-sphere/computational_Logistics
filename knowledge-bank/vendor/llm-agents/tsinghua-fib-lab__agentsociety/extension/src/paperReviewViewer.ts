/**
 * Paper review round / reviewer / meta webview — dense, verdict-first UX.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { isExtensionZh } from './i18n';
import {
  loadReviewerSummary,
  loadReviewRoundSummary,
  loadMetaReviewSummary,
  recommendationLabel,
  scoreTone,
  formatScoreShort,
  formatScoreNumber,
  findSection,
  robustnessLabel,
  rerouteLabel,
  sectionDisplayTitle,
  venueDisplayName,
  type PaperReviewerSummary,
  type PaperReviewRoundSummary,
  type PaperMetaReviewSummary,
  type ReviewBodySection,
} from './paperReviewUtils';

export class PaperReviewViewer {
  private static currentPanel: vscode.WebviewPanel | undefined;
  private static lastTarget:
    | { kind: 'round' | 'reviewer' | 'meta'; path: string }
    | undefined;

  public static reloadLanguageIfOpen(): void {
    if (!this.currentPanel || !this.lastTarget) {
      return;
    }
    const { kind, path: target } = this.lastTarget;
    void (kind === 'round'
      ? this.showRound(target)
      : kind === 'meta'
        ? this.showMeta(target)
        : this.showReviewer(target));
  }

  public static async showRound(dirPath: string): Promise<void> {
    const round = loadReviewRoundSummary(dirPath);
    if (!round) {
      vscode.window.showWarningMessage(
        isExtensionZh() ? '未找到有效的审稿轮次。' : 'No valid review round found.'
      );
      return;
    }
    const isZh = isExtensionZh();
    this.lastTarget = { kind: 'round', path: dirPath };
    this.showPanel(
      isZh ? `审稿汇总 · ${round.roundId}` : `Review · ${round.roundId}`,
      this.renderRound(round, isZh)
    );
  }

  public static async showReviewer(filePath: string): Promise<void> {
    const reviewer = loadReviewerSummary(filePath);
    if (!reviewer) {
      const meta = loadMetaReviewSummary(filePath);
      if (meta) {
        await this.showMeta(filePath);
        return;
      }
      vscode.window.showWarningMessage(
        isExtensionZh() ? '无法解析审稿文件。' : 'Could not parse reviewer file.'
      );
      return;
    }
    const isZh = isExtensionZh();
    this.lastTarget = { kind: 'reviewer', path: filePath };
    this.showPanel(
      isZh ? `${reviewer.reviewerId} · 独立审稿` : `${reviewer.reviewerId} · review`,
      this.renderReviewer(reviewer, isZh)
    );
  }

  public static async showMeta(filePath: string): Promise<void> {
    const meta = loadMetaReviewSummary(filePath);
    if (!meta) {
      vscode.window.showWarningMessage(
        isExtensionZh() ? '无法解析 MetaReview。' : 'Could not parse MetaReview.'
      );
      return;
    }
    const isZh = isExtensionZh();
    const roundDir = filePath.replace(/\.md$/i, '');
    if (fs.existsSync(roundDir) && fs.statSync(roundDir).isDirectory()) {
      await this.showRound(roundDir);
      return;
    }
    this.lastTarget = { kind: 'meta', path: filePath };
    this.showPanel(
      isZh ? `MetaReview · ${meta.roundId || path.basename(filePath)}` : 'MetaReview',
      this.renderMetaOnly(meta, isZh)
    );
  }

  private static showPanel(title: string, html: string): void {
    if (this.currentPanel) {
      this.currentPanel.title = title;
      this.currentPanel.reveal(vscode.ViewColumn.One);
      this.currentPanel.webview.html = html;
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      'paperReviewViewer',
      title,
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    this.currentPanel = panel;
    panel.onDidDispose(() => {
      this.currentPanel = undefined;
    });
    panel.webview.onDidReceiveMessage(async (msg) => {
      if (!msg || typeof msg !== 'object') {
        return;
      }
      if (msg.type === 'openEditor' && typeof msg.path === 'string' && fs.existsSync(msg.path)) {
        await vscode.window.showTextDocument(vscode.Uri.file(msg.path));
        return;
      }
      if (msg.type === 'openReview' && typeof msg.path === 'string' && fs.existsSync(msg.path)) {
        const st = fs.statSync(msg.path);
        if (st.isDirectory()) {
          await PaperReviewViewer.showRound(msg.path);
        } else {
          const base = msg.path.replace(/\.md$/i, '');
          if (
            msg.path.toLowerCase().endsWith('.md') &&
            fs.existsSync(base) &&
            fs.statSync(base).isDirectory()
          ) {
            await PaperReviewViewer.showRound(base);
          } else {
            await PaperReviewViewer.showReviewer(msg.path);
          }
        }
      }
    });
    panel.webview.html = html;
  }

  private static toneColor(tone: ReturnType<typeof scoreTone>): string {
    switch (tone) {
      case 'good':
        return '#389e0d';
      case 'mid':
        return '#d48806';
      case 'bad':
        return '#cf1322';
      default:
        return '#8c8c8c';
    }
  }

  private static esc(s: unknown): string {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  private static shell(opts: {
    title: string;
    subtitle: string;
    filePath: string;
    isZh: boolean;
    badge?: string;
    body: string;
  }): string {
    const pathLiteral = JSON.stringify(opts.filePath);
    return `<!DOCTYPE html>
<html lang="${opts.isZh ? 'zh-CN' : 'en'}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {
    --bg: var(--vscode-editor-background);
    --fg: var(--vscode-editor-foreground);
    --muted: var(--vscode-descriptionForeground);
    --border: var(--vscode-widget-border, rgba(127,127,127,.35));
    --card: var(--vscode-sideBar-background, rgba(127,127,127,.06));
    --accent: var(--vscode-textLink-foreground, #3794ff);
    --btn-bg: var(--vscode-button-secondaryBackground, transparent);
    --btn-fg: var(--vscode-button-secondaryForeground, var(--fg));
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 16px 18px 36px;
    font: 13px/1.5 var(--vscode-font-family);
    color: var(--fg);
    background: var(--bg);
    max-width: 920px;
  }
  .head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:12px; }
  .head-main { min-width:0; flex:1; }
  h1 { font-size: 17px; margin: 0 0 2px; font-weight: 650; }
  .sub { color: var(--muted); font-size: 11.5px; word-break: break-all; }
  .badge {
    display:inline-block; margin-top:6px; padding:1px 8px; border-radius:999px;
    border:1px solid var(--border); font-size:11px; color: var(--muted);
  }
  .toolbar { display:flex; gap:6px; flex-shrink:0; flex-wrap:wrap; }
  button, .link-btn {
    background: var(--btn-bg); color: var(--btn-fg);
    border: 1px solid var(--border); border-radius: 4px;
    padding: 3px 9px; cursor: pointer; font-size: 12px;
  }
  button:hover, .link-btn:hover { border-color: var(--accent); color: var(--accent); }
  .verdict {
    display:flex; gap:14px; align-items:stretch; flex-wrap:wrap;
    border:1px solid var(--border); border-radius:10px; padding:14px 16px;
    background: var(--card); margin-bottom:12px;
  }
  .verdict-score {
    min-width: 72px; text-align:center; padding-right:14px;
    border-right:1px solid var(--border);
  }
  .verdict-score .num { font-size: 34px; font-weight: 700; line-height: 1.1; letter-spacing:-0.03em; }
  .verdict-score .hint { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .verdict-main { flex:1; min-width: 200px; }
  .verdict-rec { font-size: 18px; font-weight: 650; margin: 0 0 6px; }
  .verdict-label { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; }
  .chip {
    display:inline-flex; align-items:center; gap:4px;
    padding:2px 8px; border-radius:999px; border:1px solid var(--border);
    font-size: 11.5px; background: transparent;
  }
  .chip strong { font-weight: 600; }
  .chip.warn { border-color: #d48806; color: #d48806; }
  .chip.bad { border-color: #cf1322; color: #cf1322; }
  .kv {
    display:grid; grid-template-columns: 88px 1fr; gap:4px 10px;
    font-size: 12.5px; margin: 10px 0 0;
  }
  .kv dt { color: var(--muted); }
  .kv dd { margin: 0; }
  .panel {
    border:1px solid var(--border); border-radius:8px; margin-bottom:10px; overflow:hidden;
  }
  .panel > summary, .panel-head {
    list-style:none; cursor:pointer; padding:8px 12px; font-weight:600; font-size:12.5px;
    background: var(--card); border-bottom:1px solid var(--border);
    display:flex; justify-content:space-between; align-items:center; gap:8px;
  }
  .panel > summary::-webkit-details-marker { display:none; }
  .panel > summary::after { content:"▾"; color: var(--muted); font-weight:400; }
  .panel:not([open]) > summary::after { content:"▸"; }
  .panel-body { padding: 10px 12px; }
  .panel-body.pre {
    white-space: pre-wrap; font-size: 12.5px; line-height: 1.55;
    max-height: 360px; overflow: auto;
  }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th, td { text-align:left; padding:7px 6px; border-bottom:1px solid var(--border); vertical-align:middle; }
  th { color: var(--muted); font-weight:500; font-size:11.5px; }
  tr.clickable { cursor:pointer; }
  tr.clickable:hover td { background: rgba(127,127,127,.08); }
  .pill {
    display:inline-flex; align-items:center; justify-content:center;
    min-width:26px; height:20px; padding:0 6px; border-radius:5px;
    color:#fff; font-weight:650; font-size:12px;
  }
  .tag {
    display:inline-block; padding:1px 7px; border-radius:999px;
    font-size:11px; border:1px solid var(--border); margin:0 4px 4px 0;
  }
  .muted { color: var(--muted); }
  .note {
    font-size: 11.5px; color: var(--muted); margin: 0 0 10px;
    padding: 6px 10px; border-left: 3px solid var(--border);
  }
  .sec-nav { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; }
  .sec-nav a {
    color: var(--accent); text-decoration:none; font-size:12px;
    border:1px solid var(--border); border-radius:999px; padding:2px 8px;
  }
  .sec-nav a:hover { border-color: var(--accent); }
</style>
</head>
<body>
  <div class="head">
    <div class="head-main">
      <h1>${this.esc(opts.title)}</h1>
      <div class="sub">${this.esc(opts.subtitle)}</div>
      ${opts.badge ? `<span class="badge">${this.esc(opts.badge)}</span>` : ''}
    </div>
    <div class="toolbar">
      <button type="button" onclick="copyPath()">${opts.isZh ? '复制路径' : 'Copy path'}</button>
      <button type="button" onclick="openEditor()">${opts.isZh ? '打开源文件' : 'Open source'}</button>
    </div>
  </div>
  ${opts.body}
<script>
  const FILE_PATH = ${pathLiteral};
  const vscodeApi = acquireVsCodeApi();
  function copyPath() { navigator.clipboard.writeText(FILE_PATH); }
  function openEditor() { vscodeApi.postMessage({ type: 'openEditor', path: FILE_PATH }); }
  function openReview(p) { vscodeApi.postMessage({ type: 'openReview', path: p }); }
</script>
</body>
</html>`;
  }

  private static chipsFromFacts(
    facts: { label: string; value?: string; tone?: 'warn' | 'bad' }[],
    isZh: boolean
  ): string {
    const empty = new Set([
      '—',
      isZh ? '无' : 'none',
      isZh ? '未给出' : 'n/a',
      isZh ? '未评估' : 'n/a',
    ]);
    const chips = facts
      .filter((f) => f.value && !empty.has(f.value))
      .map((f) => {
        const cls = f.tone ? `chip ${f.tone}` : 'chip';
        return `<span class="${cls}"><span class="muted">${this.esc(f.label)}</span> <strong>${this.esc(f.value)}</strong></span>`;
      });
    return chips.length ? `<div class="chips">${chips.join('')}</div>` : '';
  }

  private static sectionPanels(sections: ReviewBodySection[], isZh: boolean): string {
    const order = [
      'summary',
      'strengths',
      'concerns',
      'questions',
      'scorecard',
      'recommendation',
      'reroute',
    ] as const;
    const picked: ReviewBodySection[] = [];
    const used = new Set<string>();
    for (const kind of order) {
      const s = findSection(sections, kind);
      if (s && !used.has(s.id)) {
        picked.push(s);
        used.add(s.id);
      }
    }
    for (const s of sections) {
      if (!used.has(s.id) && s.body.trim()) {
        if (/machine-readable|handoff|json/i.test(s.title)) {
          continue;
        }
        picked.push(s);
        used.add(s.id);
      }
    }
    if (picked.length === 0) {
      return `<div class="panel"><div class="panel-head">${isZh ? '正文' : 'Body'}</div><div class="panel-body muted">${isZh ? '暂无结构化章节。' : 'No structured sections.'}</div></div>`;
    }
    const nav = `<div class="sec-nav">${picked
      .map((s) => `<a href="#sec-${this.esc(s.id)}">${this.esc(sectionDisplayTitle(s.title, isZh))}</a>`)
      .join('')}</div>`;
    const panels = picked
      .map((s, i) => {
        const open = i < 3 ? ' open' : '';
        return `<details class="panel"${open} id="sec-${this.esc(s.id)}">
          <summary>${this.esc(sectionDisplayTitle(s.title, isZh))}</summary>
          <div class="panel-body pre">${this.esc(s.body)}</div>
        </details>`;
      })
      .join('');
    return nav + panels;
  }

  private static renderRound(round: PaperReviewRoundSummary, isZh: boolean): string {
    const score = round.displayScore;
    const rec = recommendationLabel(round.displayRecommendation, isZh);
    const tone = scoreTone(score, round.venue, round.displayRecommendation);
    const scoreHint =
      round.scoreSource === 'meta'
        ? isZh
          ? 'Meta 裁决分'
          : 'Meta score'
        : round.scoreSource === 'median'
          ? isZh
            ? '三位中位分（暂无 Meta）'
            : 'Median (no Meta yet)'
          : isZh
            ? '临时均分'
            : 'Provisional mean';

    const meta = round.meta;
    const chips = this.chipsFromFacts(
      [
        {
          label: isZh ? '评审量表' : 'Venue rubric',
          value: venueDisplayName(round.venue, isZh),
        },
        {
          label: isZh ? '三位一致性' : 'Agreement',
          value: meta ? robustnessLabel(meta.robustnessStatus, isZh) : undefined,
          tone:
            meta?.robustnessStatus === 'low'
              ? 'bad'
              : meta?.robustnessStatus === 'medium'
                ? 'warn'
                : undefined,
        },
        {
          label: isZh ? '分数跨度' : 'Score span',
          value:
            meta?.scoreSpreadSteps !== undefined && meta?.scoreSpreadSteps !== null
              ? isZh
                ? `相差 ${meta.scoreSpreadSteps} 档`
                : `${meta.scoreSpreadSteps} scale steps`
              : undefined,
        },
        {
          label: isZh ? '建议回退到' : 'Suggested reopen',
          value: meta?.primaryReroute ? rerouteLabel(meta.primaryReroute, isZh) : undefined,
        },
        {
          label: isZh ? '需人工介入' : 'Needs human',
          value: meta?.adjudicationRequired ? (isZh ? '是' : 'yes') : undefined,
          tone: 'warn',
        },
      ],
      isZh
    );

    const note = !round.hasMetaReview
      ? `<p class="note">${isZh ? '尚未写出 MetaReview（应位于轮次目录旁的同名 .md）。当前为三位审稿的临时聚合，非正式 ensemble 裁决。' : 'No MetaReview yet (sibling .md next to the round folder). Scores are provisional.'}</p>`
      : `<p class="note">${isZh ? '作者侧内部模拟审稿（非官方会议结论）。下方正文来自审稿 Markdown 原文件；写得短就显示得短。' : 'Author-side internal mock review (not an official venue decision). Section text is taken verbatim from the review Markdown.'}</p>`;

    const rows = round.reviewers
      .map((r) => {
        const n = formatScoreShort(r.overall);
        const t = scoreTone(
          typeof r.overall?.value === 'number' ? r.overall.value : Number(r.overall?.value),
          r.venue || round.venue,
          r.recommendation
        );
        const pathLit = JSON.stringify(r.filePath);
        return `<tr class="clickable" onclick='openReview(${pathLit})'>
          <td><strong>${this.esc(r.reviewerId)}</strong></td>
          <td><span class="pill" style="background:${this.toneColor(t)}">${this.esc(n)}</span></td>
          <td>${this.esc(recommendationLabel(r.recommendation, isZh))}</td>
          <td class="muted">${this.esc(formatScoreShort(r.confidence))}</td>
          <td>${(r.blockingIssueIds || []).map((id) => `<span class="tag">${this.esc(id)}</span>`).join('') || '<span class="muted">—</span>'}</td>
          <td class="muted">${this.esc((r.primaryReroute && rerouteLabel(r.primaryReroute, isZh)) || '—')}</td>
        </tr>`;
      })
      .join('');

    let metaBlock = '';
    if (meta) {
      const metaScore = formatScoreShort(meta.metaScore) || formatScoreNumber(meta.scoreMedian);
      const obs =
        meta.scoreObservations && meta.scoreObservations.length
          ? meta.scoreObservations.join(' / ')
          : round.reviewers.map((r) => formatScoreShort(r.overall)).join(' / ');
      metaBlock = `
          <details class="panel" open>
            <summary>${isZh ? 'MetaReview 裁决' : 'MetaReview adjudication'}</summary>
            <div class="panel-body">
              <dl class="kv">
                <dt>${isZh ? '裁决分' : 'Meta score'}</dt><dd><strong>${this.esc(metaScore)}</strong> ${meta.metaScore?.label ? `<span class="muted">· ${this.esc(meta.metaScore.label)}</span>` : ''}</dd>
                <dt>${isZh ? '观测分' : 'Observed'}</dt><dd>${this.esc(obs)}</dd>
                <dt>${isZh ? '建议' : 'Rec.'}</dt><dd>${this.esc(recommendationLabel(meta.recommendation, isZh))}</dd>
                <dt>${isZh ? '阻塞' : 'Blocking'}</dt><dd>${(meta.blockingIssueIds || []).map((id) => `<span class="tag">${this.esc(id)}</span>`).join('') || '—'}</dd>
              </dl>
            </div>
          </details>
          ${this.sectionPanels(meta.sections, isZh)}`;
    }

    const body = `
    ${note}
    <div class="verdict">
      <div class="verdict-score">
        <div class="num" style="color:${this.toneColor(tone)}">${this.esc(formatScoreNumber(score))}</div>
        <div class="hint">${this.esc(scoreHint)}</div>
      </div>
      <div class="verdict-main">
        <div class="verdict-rec">${this.esc(rec)}</div>
        <div class="verdict-label">${isZh ? `${round.reviewerCount} 位独立审稿` : `${round.reviewerCount} independent reviews`}</div>
        ${chips}
      </div>
    </div>
    <details class="panel" open>
      <summary>${isZh ? '三位审稿对照（点击行打开）' : 'Reviewer comparison (click row)'}</summary>
      <div class="panel-body" style="padding:0">
        <table>
          <thead>
            <tr>
              <th>${isZh ? '审稿人' : 'Rev'}</th>
              <th>${isZh ? '分数' : 'Score'}</th>
              <th>${isZh ? '建议' : 'Rec'}</th>
              <th>${isZh ? '置信' : 'Conf'}</th>
              <th>${isZh ? '阻塞' : 'Block'}</th>
              <th>${isZh ? '建议回退' : 'Reopen'}</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </details>
    ${metaBlock}`;

    return this.shell({
      title: isZh ? `审稿汇总 · ${round.roundId}` : `Review round · ${round.roundId}`,
      subtitle: round.dirPath,
      filePath: meta?.filePath || round.dirPath,
      isZh,
      badge: isZh ? '作者侧 Internal Mock Review' : 'Author-side Internal Mock Review',
      body,
    });
  }

  private static renderReviewer(reviewer: PaperReviewerSummary, isZh: boolean): string {
    const n = formatScoreShort(reviewer.overall);
    const tone = scoreTone(
      typeof reviewer.overall?.value === 'number'
        ? reviewer.overall.value
        : Number(reviewer.overall?.value),
      reviewer.venue,
      reviewer.recommendation
    );
    const rec = recommendationLabel(reviewer.recommendation, isZh);
    const chips = this.chipsFromFacts(
      [
        {
          label: isZh ? '评审量表' : 'Venue rubric',
          value: venueDisplayName(reviewer.venue, isZh),
        },
        {
          label: isZh ? '置信度' : 'Confidence',
          value:
            formatScoreShort(reviewer.confidence) !== '—'
              ? formatScoreShort(reviewer.confidence)
              : undefined,
        },
        {
          label: isZh ? '建议回退到' : 'Suggested reopen',
          value: reviewer.primaryReroute
            ? rerouteLabel(reviewer.primaryReroute, isZh)
            : undefined,
        },
        {
          label: isZh ? '阻塞项' : 'Blocking',
          value: (reviewer.blockingIssueIds || []).length
            ? (reviewer.blockingIssueIds || []).join(', ')
            : undefined,
          tone: 'bad',
        },
      ],
      isZh
    );

    const roundDir = path.dirname(reviewer.filePath);
    const body = `
    <p class="note">${isZh ? '这是三位独立审稿之一，非正式最终裁决。' : 'One of three independent reviews — not the final ensemble decision.'}
button type="button" class="link-btn" style="margin-left:8px" onclick='openReview(${JSON.stringify(roundDir)})'>${isZh ? '查看轮次汇总' : 'Round summary'}</button></p>
    <div class="verdict">
      <div class="verdict-score">
        <div class="num" style="color:${this.toneColor(tone)}">${this.esc(n)}</div>
        <div class="hint">${isZh ? '总体分' : 'Overall'}</div>
      </div>
      <div class="verdict-main">
        <div class="verdict-rec">${this.esc(rec)}</div>
        <div class="verdict-label">${this.esc(reviewer.overall?.label || reviewer.title || '')}</div>
        ${chips}
        ${
          (reviewer.secondaryReroutes || []).length
            ? `<div style="margin-top:8px">${(reviewer.secondaryReroutes || [])
                .map((r) => `<span class="tag">${this.esc(rerouteLabel(r, isZh))}</span>`)
                .join('')}</div>`
            : ''
        }
      </div>
    </div>
    ${this.sectionPanels(reviewer.sections, isZh)}`;

    return this.shell({
      title: isZh
        ? `${reviewer.reviewerId} · 独立审稿`
        : `${reviewer.reviewerId} · Independent review`,
      subtitle: reviewer.filePath,
      filePath: reviewer.filePath,
      isZh,
      badge: reviewer.roundId || undefined,
      body,
    });
  }

  private static renderMetaOnly(meta: PaperMetaReviewSummary, isZh: boolean): string {
    const score = formatScoreShort(meta.metaScore) || formatScoreNumber(meta.scoreMedian);
    const tone = scoreTone(
      typeof meta.metaScore?.value === 'number'
        ? meta.metaScore.value
        : Number(meta.metaScore?.value ?? meta.scoreMedian),
      meta.venue,
      meta.recommendation
    );
    const chips = this.chipsFromFacts(
      [
        {
          label: isZh ? '评审量表' : 'Venue rubric',
          value: venueDisplayName(meta.venue, isZh),
        },
        {
          label: isZh ? '三位一致性' : 'Agreement',
          value: robustnessLabel(meta.robustnessStatus, isZh),
          tone: meta.robustnessStatus === 'low' ? 'bad' : undefined,
        },
        {
          label: isZh ? '建议回退到' : 'Suggested reopen',
          value: meta.primaryReroute ? rerouteLabel(meta.primaryReroute, isZh) : undefined,
        },
      ],
      isZh
    );
    const body = `
    <div class="verdict">
      <div class="verdict-score">
        <div class="num" style="color:${this.toneColor(tone)}">${this.esc(score)}</div>
        <div class="hint">${isZh ? 'Meta 裁决' : 'Meta score'}</div>
      </div>
      <div class="verdict-main">
        <div class="verdict-rec">${this.esc(recommendationLabel(meta.recommendation, isZh))}</div>
        <div class="verdict-label">${this.esc(meta.metaScore?.label || '')}</div>
        ${chips}
      </div>
    </div>
    ${this.sectionPanels(meta.sections, isZh)}`;
    return this.shell({
      title: isZh ? `MetaReview · ${meta.roundId || ''}` : 'MetaReview',
      subtitle: meta.filePath,
      filePath: meta.filePath,
      isZh,
      body,
    });
  }
}
