'use strict';

const fs = require('fs');
const path = require('path');

function writeCoverageMarkdown(coverage, config) {
  const lines = renderCoverageMarkdown(coverage);
  const outPath = path.join(process.cwd(), config.output.dir, 'coverage.md');
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, lines.join('\n'), 'utf8');
  return outPath;
}

function renderCoverageMarkdown(coverage) {
  const summary = coverage.summary || {};
  const lines = [];

  lines.push('# qa-probe Coverage');
  lines.push(`**Generated:** ${coverage.generatedAt || new Date().toISOString()}`);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push(`- Dead endpoints: ${summary.deadEndpointCount || 0}`);
  lines.push(`- Dead components: ${summary.deadComponentCount || 0}`);
  lines.push(`- Orphaned response fields: ${summary.orphanedFieldCount || 0}`);
  lines.push('');

  lines.push('## Dead Endpoints');
  lines.push('');
  if ((coverage.deadEndpoints || []).length === 0) {
    lines.push('No OpenAPI endpoints were found without frontend references.');
  } else {
    lines.push('| Endpoint | Tags | Summary |');
    lines.push('|---|---|---|');
    for (const item of coverage.deadEndpoints) {
      lines.push(`| \`${item.endpoint}\` | ${escapeCell((item.tags || []).join(', '))} | ${escapeCell(item.summary || '')} |`);
    }
  }
  lines.push('');

  lines.push('## Dead Components');
  lines.push('');
  if ((coverage.deadComponents || []).length === 0) {
    lines.push('No frontend files were found that only call endpoints outside the spec or endpoints returning 404.');
  } else {
    lines.push('| File | Reason | Endpoints |');
    lines.push('|---|---|---|');
    for (const item of coverage.deadComponents) {
      lines.push(`| \`${item.file}\` | \`${item.reason}\` | ${escapeCell((item.endpoints || []).join(', '))} |`);
    }
  }
  lines.push('');

  lines.push('## Orphaned Response Fields');
  lines.push('');
  if ((coverage.orphanedFields || []).length === 0) {
    lines.push('No returned fields were found without known frontend reads.');
  } else {
    lines.push('| Endpoint | Returned But Unread | Frontend Reads |');
    lines.push('|---|---|---|');
    for (const item of coverage.orphanedFields) {
      lines.push(`| \`${item.endpoint}\` | ${escapeCell((item.fields || []).join(', '))} | ${escapeCell((item.readFields || []).join(', '))} |`);
    }
  }
  lines.push('');

  return lines;
}

function escapeCell(value) {
  return String(value || '').replace(/\|/g, '\\|').replace(/\n/g, ' ').slice(0, 200);
}

module.exports = { writeCoverageMarkdown, renderCoverageMarkdown };
