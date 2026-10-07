/**
 * Helpers for paper-review sidebar + viewer
 * (agentsociety.paper-review.individual/v1 + meta/v1).
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

export type ScoreValue = { value?: number | string; label?: string };

export type PaperReviewerSummary = {
  filePath: string;
  fileName: string;
  reviewerId: string;
  title?: string;
  venue?: string;
  roundId?: string;
  overall?: ScoreValue;
  confidence?: ScoreValue;
  recommendation?: string;
  primaryReroute?: string;
  secondaryReroutes?: string[];
  blockingIssueIds?: string[];
  reviewedAt?: string;
  bodyMarkdown: string;
  sections: ReviewBodySection[];
  frontmatter: Record<string, unknown>;
};

export type ReviewBodySection = {
  id: string;
  title: string;
  body: string;
};

export type PaperMetaReviewSummary = {
  filePath: string;
  roundId?: string;
  venue?: string;
  scoreMedian?: number;
  scoreSpreadSteps?: number;
  scoreObservations?: number[];
  metaScore?: ScoreValue;
  confidence?: ScoreValue;
  recommendation?: string;
  recommendationVotes?: string[];
  primaryReroute?: string;
  secondaryReroutes?: string[];
  blockingIssueIds?: string[];
  robustnessStatus?: string;
  adjudicationRequired?: boolean;
  concernAgreement?: Record<string, number>;
  bodyMarkdown: string;
  sections: ReviewBodySection[];
  frontmatter: Record<string, unknown>;
};

export type PaperReviewRoundSummary = {
  dirPath: string;
  dirName: string;
  roundId: string;
  venue?: string;
  reviewerCount: number;
  reviewers: PaperReviewerSummary[];
  /** Temporary individual mean; prefer displayScore / meta. */
  meanScore?: number;
  medianScore?: number;
  displayScore?: number;
  scoreSource: 'meta' | 'median' | 'mean' | 'none';
  dominantRecommendation?: string;
  displayRecommendation?: string;
  hasMetaReview: boolean;
  metaReviewPath?: string;
  meta?: PaperMetaReviewSummary;
};

const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;

const SECTION_ALIASES: Record<string, string[]> = {
  summary: ['paper summary', 'summary', 'review target', '论文摘要', '摘要'],
  strengths: ['strengths', 'strong points', '优点', '优势'],
  concerns: [
    'concerns',
    'weaknesses',
    'weak points',
    'numbered concerns',
    '问题',
    '弱点',
    '不足',
  ],
  questions: ['questions', 'questions and score-change conditions', '问题与改分条件'],
  recommendation: [
    'overall recommendation',
    'overall recommendation and confidence',
    'rating',
    '总体建议',
    '总评',
  ],
  reroute: ['advisory reroute', 'reroute', '建议重路由'],
  scorecard: ['venue scorecard', 'metareview venue scorecard', '分项评分'],
};

export function parseMarkdownFrontmatter(text: string): {
  frontmatter: Record<string, unknown>;
  body: string;
} {
  const match = text.match(FRONTMATTER_RE);
  if (!match) {
    return { frontmatter: {}, body: text };
  }
  try {
    const loaded = yaml.load(match[1]);
    const frontmatter =
      loaded && typeof loaded === 'object' && !Array.isArray(loaded)
        ? (loaded as Record<string, unknown>)
        : {};
    return { frontmatter, body: text.slice(match[0].length) };
  } catch {
    return { frontmatter: {}, body: text };
  }
}

/** Split markdown body into ## / # sections for denser viewer navigation. */
export function extractReviewBodySections(body: string): ReviewBodySection[] {
  const lines = body.replace(/\r\n/g, '\n').split('\n');
  const sections: ReviewBodySection[] = [];
  let currentTitle = '';
  let currentLines: string[] = [];
  const flush = () => {
    const text = currentLines.join('\n').trim();
    if (!currentTitle && !text) {
      return;
    }
    const title = currentTitle || 'Overview';
    sections.push({
      id: slugify(title),
      title,
      body: text,
    });
  };
  for (const line of lines) {
    const heading = line.match(/^#{1,3}\s+(.+?)\s*$/);
    if (heading) {
      flush();
      currentTitle = heading[1].replace(/^#+\s*/, '').trim();
      currentLines = [];
      continue;
    }
    currentLines.push(line);
  }
  flush();
  return sections.filter((s) => s.body.length > 0 || s.title !== 'Overview');
}

function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 48);
}

export function findSection(
  sections: ReviewBodySection[],
  kind: keyof typeof SECTION_ALIASES
): ReviewBodySection | undefined {
  const aliases = SECTION_ALIASES[kind] || [];
  return sections.find((s) => {
    const t = s.title.toLowerCase();
    return aliases.some((a) => t === a || t.includes(a));
  });
}

function asScore(raw: unknown): ScoreValue | undefined {
  if (raw === null || raw === undefined) {
    return undefined;
  }
  if (typeof raw === 'number' || typeof raw === 'string') {
    return { value: raw };
  }
  if (typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    return {
      value: obj.value as number | string | undefined,
      label: typeof obj.label === 'string' ? obj.label : undefined,
    };
  }
  return undefined;
}

function numericScore(score?: ScoreValue): number | undefined {
  if (!score || score.value === null || score.value === undefined || score.value === '') {
    return undefined;
  }
  const n = typeof score.value === 'number' ? score.value : Number(score.value);
  return Number.isFinite(n) ? n : undefined;
}

function median(nums: number[]): number | undefined {
  if (nums.length === 0) {
    return undefined;
  }
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}

export function recommendationLabel(raw: string | undefined, isZh: boolean): string {
  if (!raw) {
    return isZh ? '未给出' : 'n/a';
  }
  const key = raw.toLowerCase().replace(/[\s-]+/g, '_');
  const mapZh: Record<string, string> = {
    strong_accept: '强接收',
    accept: '接收',
    weak_accept: '弱接收',
    borderline_accept: '边缘接收',
    borderline: '边缘',
    findings: 'Findings',
    revise_and_resubmit: '大修重投',
    major_revision: '大修',
    minor_revision: '小修',
    weak_reject: '弱拒',
    reject: '拒稿',
    strong_reject: '强拒',
  };
  const mapEn: Record<string, string> = {
    strong_accept: 'Strong accept',
    accept: 'Accept',
    weak_accept: 'Weak accept',
    borderline_accept: 'Borderline accept',
    borderline: 'Borderline',
    findings: 'Findings',
    revise_and_resubmit: 'Revise & resubmit',
    major_revision: 'Major revision',
    minor_revision: 'Minor revision',
    weak_reject: 'Weak reject',
    reject: 'Reject',
    strong_reject: 'Strong reject',
  };
  return (isZh ? mapZh : mapEn)[key] || raw.replace(/_/g, ' ');
}

export function recommendationTone(
  recommendation?: string
): 'good' | 'mid' | 'bad' | 'unknown' {
  if (!recommendation) {
    return 'unknown';
  }
  const key = recommendation.toLowerCase().replace(/[\s-]+/g, '_');
  if (
    ['strong_accept', 'accept', 'weak_accept', 'findings', 'minor_revision'].includes(key)
  ) {
    return 'good';
  }
  if (
    ['borderline', 'borderline_accept', 'revise_and_resubmit', 'major_revision'].includes(
      key
    )
  ) {
    return 'mid';
  }
  if (['weak_reject', 'reject', 'strong_reject'].includes(key)) {
    return 'bad';
  }
  return 'unknown';
}

/** Venue-aware score color: prefer recommendation when present. */
export function scoreTone(
  score?: number,
  venue?: string,
  recommendation?: string
): 'good' | 'mid' | 'bad' | 'unknown' {
  const fromRec = recommendationTone(recommendation);
  if (fromRec !== 'unknown') {
    return fromRec;
  }
  if (score === null || score === undefined || !Number.isFinite(score)) {
    return 'unknown';
  }
  const v = (venue || '').toLowerCase();
  // ICLR public form: 2/4/6/8/10
  if (v === 'iclr' || score > 6) {
    if (score >= 8) {
      return 'good';
    }
    if (score >= 6) {
      return 'mid';
    }
    return 'bad';
  }
  // NeurIPS / ICML: 1–6
  if (v === 'neurips' || v === 'nips' || v === 'icml') {
    if (score >= 5) {
      return 'good';
    }
    if (score >= 4) {
      return 'mid';
    }
    return 'bad';
  }
  // Generic / ACL ARR / AAAI project-local: ~1–5
  if (score >= 4) {
    return 'good';
  }
  if (score >= 3) {
    return 'mid';
  }
  return 'bad';
}

export function formatScoreShort(score?: ScoreValue): string {
  const n = numericScore(score);
  if (n === null || n === undefined) {
    return '—';
  }
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function formatScoreNumber(n?: number): string {
  if (n === null || n === undefined || !Number.isFinite(n)) {
    return '—';
  }
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function isNoiseReviewFile(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  if (/invalid-attempt/i.test(lower)) {
    return true;
  }
  if (/^ensemble-status\.md$/i.test(lower)) {
    return true;
  }
  if (/^(meta[-_]?review|summary)/i.test(lower)) {
    return true;
  }
  if (lower === 'input-manifest.yaml' || lower === 'input-manifest.yml') {
    return true;
  }
  return false;
}

function isIndividualReviewFile(fileName: string, frontmatter: Record<string, unknown>): boolean {
  if (/^reviewer[-_]?\d+\.md$/i.test(fileName) || /^r\d+\.md$/i.test(fileName)) {
    return true;
  }
  const schema = String(frontmatter.schema || '');
  if (schema.includes('paper-review.individual')) {
    return true;
  }
  return Boolean(frontmatter.reviewer_id && frontmatter.overall_score);
}

/** Sibling MetaReview path: paper/reviews/<dirName>.md */
export function resolveSiblingMetaReviewPath(roundDir: string): string | undefined {
  const sibling = `${roundDir.replace(/[/\\]+$/, '')}.md`;
  if (fs.existsSync(sibling) && fs.statSync(sibling).isFile()) {
    return sibling;
  }
  return undefined;
}

export function loadReviewerSummary(filePath: string): PaperReviewerSummary | undefined {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return undefined;
  }
  const fileName = path.basename(filePath);
  if (isNoiseReviewFile(fileName) || !fileName.toLowerCase().endsWith('.md')) {
    return undefined;
  }
  const text = fs.readFileSync(filePath, 'utf-8');
  const { frontmatter, body } = parseMarkdownFrontmatter(text);
  if (!isIndividualReviewFile(fileName, frontmatter)) {
    return undefined;
  }
  const schema = String(frontmatter.schema || '');
  if (schema.includes('paper-review.meta')) {
    return undefined;
  }
  const reviewerId = String(
    frontmatter.reviewer_id ||
      fileName.replace(/^reviewer[-_]?/i, 'R').replace(/\.md$/i, '') ||
      fileName
  );
  return {
    filePath,
    fileName,
    reviewerId,
    title: typeof frontmatter.title === 'string' ? frontmatter.title : undefined,
    venue: typeof frontmatter.venue === 'string' ? frontmatter.venue : undefined,
    roundId: typeof frontmatter.round_id === 'string' ? frontmatter.round_id : undefined,
    overall: asScore(frontmatter.overall_score),
    confidence: asScore(frontmatter.confidence),
    recommendation:
      typeof frontmatter.recommendation === 'string' ? frontmatter.recommendation : undefined,
    primaryReroute:
      typeof frontmatter.primary_reroute === 'string' ? frontmatter.primary_reroute : undefined,
    secondaryReroutes: Array.isArray(frontmatter.secondary_reroutes)
      ? frontmatter.secondary_reroutes.map(String)
      : undefined,
    blockingIssueIds: Array.isArray(frontmatter.blocking_issue_ids)
      ? frontmatter.blocking_issue_ids.map(String)
      : undefined,
    reviewedAt: typeof frontmatter.reviewed_at === 'string' ? frontmatter.reviewed_at : undefined,
    bodyMarkdown: body,
    sections: extractReviewBodySections(body),
    frontmatter,
  };
}

export function loadMetaReviewSummary(filePath: string): PaperMetaReviewSummary | undefined {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return undefined;
  }
  const text = fs.readFileSync(filePath, 'utf-8');
  const { frontmatter, body } = parseMarkdownFrontmatter(text);
  const schema = String(frontmatter.schema || '');
  if (schema && !schema.includes('paper-review.meta')) {
    if (frontmatter.score_median === null || frontmatter.score_median === undefined) {
      if (!frontmatter.meta_score) {
        return undefined;
      }
    }
  }
  const votes = Array.isArray(frontmatter.recommendation_votes)
    ? frontmatter.recommendation_votes.map(String)
    : undefined;
  let recommendation: string | undefined;
  if (typeof frontmatter.recommendation === 'string') {
    recommendation = frontmatter.recommendation;
  } else if (votes && votes.length) {
    const counts = new Map<string, number>();
    for (const v of votes) {
      counts.set(v, (counts.get(v) || 0) + 1);
    }
    let best = 0;
    for (const [k, c] of counts) {
      if (c > best) {
        best = c;
        recommendation = k;
      }
    }
  }

  const concernAgreement =
    frontmatter.concern_agreement &&
    typeof frontmatter.concern_agreement === 'object' &&
    !Array.isArray(frontmatter.concern_agreement)
      ? (frontmatter.concern_agreement as Record<string, number>)
      : undefined;

  return {
    filePath,
    roundId: typeof frontmatter.round_id === 'string' ? frontmatter.round_id : undefined,
    venue: typeof frontmatter.venue === 'string' ? frontmatter.venue : undefined,
    scoreMedian:
      typeof frontmatter.score_median === 'number'
        ? frontmatter.score_median
        : Number.isFinite(Number(frontmatter.score_median))
          ? Number(frontmatter.score_median)
          : undefined,
    scoreSpreadSteps:
      typeof frontmatter.score_spread_steps === 'number'
        ? frontmatter.score_spread_steps
        : undefined,
    scoreObservations: Array.isArray(frontmatter.score_observations)
      ? frontmatter.score_observations.map(Number).filter((n) => Number.isFinite(n))
      : undefined,
    metaScore: asScore(frontmatter.meta_score),
    confidence: asScore(frontmatter.confidence),
    recommendation,
    recommendationVotes: votes,
    primaryReroute:
      typeof frontmatter.primary_reroute === 'string' ? frontmatter.primary_reroute : undefined,
    secondaryReroutes: Array.isArray(frontmatter.secondary_reroutes)
      ? frontmatter.secondary_reroutes.map(String)
      : undefined,
    blockingIssueIds: Array.isArray(frontmatter.blocking_issue_ids)
      ? frontmatter.blocking_issue_ids.map(String)
      : undefined,
    robustnessStatus:
      typeof frontmatter.robustness_status === 'string'
        ? frontmatter.robustness_status
        : undefined,
    adjudicationRequired: Boolean(frontmatter.adjudication_required),
    concernAgreement,
    bodyMarkdown: body,
    sections: extractReviewBodySections(body),
    frontmatter,
  };
}

function resolveMetaPath(dirPath: string, entries: string[]): string | undefined {
  const sibling = resolveSiblingMetaReviewPath(dirPath);
  if (sibling) {
    return sibling;
  }
  const inner = entries.find((e) => /^(meta[-_]?review|summary)/i.test(e));
  if (inner) {
    return path.join(dirPath, inner);
  }
  return undefined;
}

export function loadReviewRoundSummary(dirPath: string): PaperReviewRoundSummary | undefined {
  if (!fs.existsSync(dirPath) || !fs.statSync(dirPath).isDirectory()) {
    return undefined;
  }
  const dirName = path.basename(dirPath);
  const entries = fs.readdirSync(dirPath);
  const reviewers: PaperReviewerSummary[] = [];
  for (const entry of entries) {
    if (!entry.toLowerCase().endsWith('.md') || isNoiseReviewFile(entry)) {
      continue;
    }
    const full = path.join(dirPath, entry);
    const summary = loadReviewerSummary(full);
    if (summary) {
      reviewers.push(summary);
    }
  }
  reviewers.sort((a, b) => a.reviewerId.localeCompare(b.reviewerId, undefined, { numeric: true }));

  const scores = reviewers
    .map((r) => numericScore(r.overall))
    .filter((n): n is number => typeof n === 'number');
  const meanScore =
    scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : undefined;
  const medianScore = median(scores);

  const recCounts = new Map<string, number>();
  for (const r of reviewers) {
    if (!r.recommendation) {
      continue;
    }
    recCounts.set(r.recommendation, (recCounts.get(r.recommendation) || 0) + 1);
  }
  let dominantRecommendation: string | undefined;
  let best = 0;
  for (const [k, v] of recCounts) {
    if (v > best) {
      best = v;
      dominantRecommendation = k;
    }
  }

  const metaReviewPath = resolveMetaPath(dirPath, entries);
  const meta = metaReviewPath ? loadMetaReviewSummary(metaReviewPath) : undefined;

  let roundId = dirName;
  let venue: string | undefined = meta?.venue || reviewers[0]?.venue;
  const manifestPath = path.join(dirPath, 'input-manifest.yaml');
  if (fs.existsSync(manifestPath)) {
    try {
      const raw = yaml.load(fs.readFileSync(manifestPath, 'utf-8')) as Record<string, unknown>;
      if (typeof raw?.round_id === 'string') {
        roundId = raw.round_id;
      }
      if (typeof raw?.venue === 'string') {
        venue = raw.venue;
      }
    } catch {
      /* ignore */
    }
  } else if (meta?.roundId) {
    roundId = meta.roundId;
  } else if (reviewers[0]?.roundId) {
    roundId = reviewers[0].roundId;
  }

  let displayScore: number | undefined;
  let scoreSource: PaperReviewRoundSummary['scoreSource'] = 'none';
  if (meta?.metaScore && numericScore(meta.metaScore) !== undefined) {
    displayScore = numericScore(meta.metaScore);
    scoreSource = 'meta';
  } else if (typeof meta?.scoreMedian === 'number') {
    displayScore = meta.scoreMedian;
    scoreSource = 'meta';
  } else if (typeof medianScore === 'number') {
    displayScore = medianScore;
    scoreSource = 'median';
  } else if (typeof meanScore === 'number') {
    displayScore = meanScore;
    scoreSource = 'mean';
  }

  const displayRecommendation =
    meta?.recommendation || dominantRecommendation;

  return {
    dirPath,
    dirName,
    roundId,
    venue,
    reviewerCount: reviewers.length,
    reviewers,
    meanScore,
    medianScore,
    displayScore,
    scoreSource,
    dominantRecommendation,
    displayRecommendation,
    hasMetaReview: Boolean(meta),
    metaReviewPath: meta ? meta.filePath : metaReviewPath,
    meta,
  };
}

export function listReviewRoundDirs(reviewsDir: string): PaperReviewRoundSummary[] {
  if (!fs.existsSync(reviewsDir) || !fs.statSync(reviewsDir).isDirectory()) {
    return [];
  }
  const rounds: PaperReviewRoundSummary[] = [];
  for (const entry of fs.readdirSync(reviewsDir)) {
    const full = path.join(reviewsDir, entry);
    if (!fs.statSync(full).isDirectory()) {
      continue;
    }
    const summary = loadReviewRoundSummary(full);
    if (summary && summary.reviewers.length > 0) {
      rounds.push(summary);
    }
  }
  rounds.sort((a, b) => b.dirName.localeCompare(a.dirName, undefined, { numeric: true }));
  return rounds;
}

export function roundTreeDescription(round: PaperReviewRoundSummary, isZh: boolean): string {
  const parts: string[] = [];
  if (typeof round.displayScore === 'number') {
    const prefix =
      round.scoreSource === 'meta'
        ? isZh
          ? '裁决'
          : 'meta'
        : round.scoreSource === 'median'
          ? isZh
            ? '中位'
            : 'med'
          : isZh
            ? '均'
            : 'avg';
    parts.push(`${prefix} ${formatScoreNumber(round.displayScore)}`);
  }
  parts.push(isZh ? `${round.reviewerCount} 位` : `${round.reviewerCount} rev`);
  if (round.displayRecommendation) {
    parts.push(recommendationLabel(round.displayRecommendation, isZh));
  }
  if (round.meta?.robustnessStatus) {
    parts.push(round.meta.robustnessStatus);
  }
  return parts.join(' · ');
}

export function reviewerTreeDescription(
  reviewer: PaperReviewerSummary,
  _isZh: boolean
): string {
  const score = formatScoreShort(reviewer.overall);
  const rec = recommendationLabel(reviewer.recommendation, _isZh);
  return `${score} · ${rec}`;
}

export function robustnessLabel(status: string | undefined, isZh: boolean): string {
  if (!status) {
    return isZh ? '未评估' : 'n/a';
  }
  const key = status.toLowerCase();
  const zh: Record<string, string> = {
    high: '三位高度一致',
    medium: '大体一致、有分歧',
    low: '分歧大/需人工',
  };
  const en: Record<string, string> = {
    high: 'High agreement',
    medium: 'Some disagreement',
    low: 'Low agreement / needs human',
  };
  return (isZh ? zh : en)[key] || status;
}

export function rerouteLabel(raw: string | undefined, isZh: boolean): string {
  if (!raw) {
    return isZh ? '无' : 'none';
  }
  const key = raw.toLowerCase().replace(/[\s-]+/g, '_');
  const zh: Record<string, string> = {
    literature_search: '回文献检索',
    hypothesis: '回假设修订',
    experiment_config: '回实验设计',
    run_experiment: '回补跑实验',
    analysis: '回数据分析',
    generate_paper: '回论文改写',
    human_decision: '需人工决策',
    none: '无需回退',
    // legacy / short aliases
    literature: '回文献检索',
    experiment: '回实验设计',
    typeset: '回排版',
    human: '需人工决策',
  };
  const en: Record<string, string> = {
    literature_search: 'Literature',
    hypothesis: 'Hypothesis',
    experiment_config: 'Experiment design',
    run_experiment: 'Re-run experiments',
    analysis: 'Analysis',
    generate_paper: 'Paper writing',
    human_decision: 'Human decision',
    none: 'None',
  };
  return (isZh ? zh : en)[key] || raw.replace(/_/g, ' ');
}

/** Display title for review body sections (file may be English). */
export function sectionDisplayTitle(title: string, isZh: boolean): string {
  if (!isZh) {
    return title;
  }
  const t = title.toLowerCase().trim();
  const map: Array<[RegExp, string]> = [
    [/^paper summary$|^summary$/, '论文摘要'],
    [/^strengths$|^strong points$/, '优点'],
    [/^concerns$|^weaknesses$|^weak points$|^numbered concerns$/, '主要问题'],
    [/^questions/, '问题与改分条件'],
    [/scorecard/, '分项评分'],
    [/^overall recommendation/, '总体建议'],
    [/^advisory reroute$|^reroute$/, '建议回退阶段'],
    [/^review target$/, '审稿对象'],
    [/^claimed contributions$/, '声称贡献'],
    [/^limitations/, '局限与伦理'],
    [/^internal mock/, '内部模拟审稿'],
  ];
  for (const [re, label] of map) {
    if (re.test(t)) {
      return label;
    }
  }
  return title;
}

export function venueDisplayName(venue: string | undefined, isZh: boolean): string | undefined {
  if (!venue) {
    return undefined;
  }
  const key = venue.toLowerCase();
  const zh: Record<string, string> = {
    generic: '通用量表（非特定会议）',
    iclr: 'ICLR',
    neurips: 'NeurIPS',
    nips: 'NeurIPS',
    icml: 'ICML',
    'acl-arr': 'ACL ARR',
    acl: 'ACL ARR',
    aaai: 'AAAI（项目本地分）',
  };
  if (isZh) {
    return zh[key] || venue.toUpperCase();
  }
  if (key === 'generic') {
    return 'Generic rubric';
  }
  return venue.toUpperCase();
}
